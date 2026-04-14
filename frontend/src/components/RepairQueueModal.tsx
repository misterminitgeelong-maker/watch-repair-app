import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X, ChevronRight, SkipForward, StickyNote, Wrench, CheckCheck,
  MessageSquare, Filter, ExternalLink,
} from 'lucide-react'
import {
  listJobs, updateJobStatus, addJobNote, claimJob, releaseJob, resendJobNotification,
  listShoeRepairJobs, updateShoeRepairJobStatus, addShoeJobNote, claimShoeJob, releaseShoeJob, resendShoeNotification,
  getJob, getShoeRepairJob,
  type RepairJob, type ShoeRepairJob, type JobStatus,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Spinner } from '@/components/ui'
import { STATUS_LABELS } from '@/lib/utils'
import { Link } from 'react-router-dom'

// ── Types ──────────────────────────────────────────────────────────────────────

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
  claimed_by_user_id?: string | null
  claimed_by_name?: string | null
}

interface Props {
  mode: 'watch' | 'shoe'
  onClose: () => void
}

type CardState = 'view' | 'advance' | 'note' | 'noUpdate'

interface SessionStats {
  advanced: number
  checkedIn: number
  skipped: number
}

// ── Constants ──────────────────────────────────────────────────────────────────

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 }

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#C0392B', high: '#D4693A', normal: '#7A5D2E', low: '#8A7563',
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

// Statuses where a "remind customer" SMS makes sense
const SMS_REMIND_STATUSES = new Set(['awaiting_go_ahead', 'completed', 'awaiting_collection'])

const EXCLUDE_STATUSES = new Set(['collected', 'no_go'])
const SWIPE_THRESHOLD = 80

const ALL_PRIORITIES = ['urgent', 'high', 'normal', 'low']
const QUEUE_STATUSES = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on', 'completed', 'awaiting_collection']

// ── Helpers ────────────────────────────────────────────────────────────────────

function getCollectionUrgency(collectionDate?: string): number {
  if (!collectionDate) return 3
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1)
  const d = new Date(collectionDate)
  if (d < today) return 0  // OVERDUE
  if (d <= today) return 1  // today (same day, after midnight check)
  if (d <= tomorrow) return 2  // tomorrow
  return 3
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

// ── Component ──────────────────────────────────────────────────────────────────

export default function RepairQueueModal({ mode, onClose }: Props) {
  const qc = useQueryClient()
  const { sessionUserId: userId } = useAuth()

  // ── Queue state ───────────────────────────────────────────────────────────
  const [queueOrder, setQueueOrder] = useState<string[] | null>(null)
  const [done, setDone] = useState<Set<string>>(new Set())
  const [stats, setStats] = useState<SessionStats>({ advanced: 0, checkedIn: 0, skipped: 0 })

  // ── Filter state ──────────────────────────────────────────────────────────
  const [showFilters, setShowFilters] = useState(false)
  const [filterStatuses, setFilterStatuses] = useState<Set<string>>(new Set())
  const [filterPriorities, setFilterPriorities] = useState<Set<string>>(new Set())
  const [filterDueToday, setFilterDueToday] = useState(false)

  // ── Card/panel state ──────────────────────────────────────────────────────
  const [cardState, setCardState] = useState<CardState>('view')
  const [selectedNote, setSelectedNote] = useState('')
  const [customNote, setCustomNote] = useState('')
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [smsSending, setSmsSending] = useState(false)
  const [smsResult, setSmsResult] = useState<string | null>(null)

  // ── Swipe state ───────────────────────────────────────────────────────────
  const [dragX, setDragX] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const dragStartX = useRef<number | null>(null)
  const pointerIdRef = useRef<number | null>(null)
  const capturedRef = useRef(false)
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
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, collection_date: j.collection_date, customer_name: j.customer_name, description: j.description, type: 'watch' as const, claimed_by_user_id: j.claimed_by_user_id, claimed_by_name: j.claimed_by_name }))
    : ((shoeQuery.data ?? []) as ShoeRepairJob[])
        .filter(j => !EXCLUDE_STATUSES.has(j.status))
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, collection_date: j.collection_date, customer_name: undefined, description: j.description, items: j.items?.map(i => i.item_name).filter(Boolean), quote_status: j.quote_status, type: 'shoe' as const, claimed_by_user_id: j.claimed_by_user_id, claimed_by_name: j.claimed_by_name }))

  // Apply filters
  const filteredJobs = allJobs.filter(j => {
    if (filterStatuses.size > 0 && !filterStatuses.has(j.status)) return false
    if (filterPriorities.size > 0 && !filterPriorities.has(j.priority)) return false
    if (filterDueToday) {
      const urg = getCollectionUrgency(j.collection_date)
      if (urg > 1) return false
    }
    return true
  })

  useEffect(() => {
    if (filteredJobs.length > 0 && queueOrder === null) {
      setQueueOrder(sortQueue(filteredJobs).map(j => j.id))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredJobs.length, queueOrder])

  const jobMap = Object.fromEntries(filteredJobs.map(j => [j.id, j]))
  const visibleIds = (queueOrder ?? []).filter(id => !done.has(id) && jobMap[id])
  const currentId = visibleIds[0] ?? null
  const current = currentId ? jobMap[currentId] : null
  const remaining = visibleIds.length
  const doneCount = done.size
  const isMyClaim = currentId ? current?.claimed_by_user_id === userId : false
  const isOthersClaim = current?.claimed_by_user_id && current.claimed_by_user_id !== userId
  const filterCount = filterStatuses.size + filterPriorities.size + (filterDueToday ? 1 : 0)

  // ── Detail query ──────────────────────────────────────────────────────────
  const detailQuery = useQuery({
    queryKey: ['job-detail', detailJobId, mode],
    queryFn: () => detailJobId
      ? (mode === 'watch' ? getJob(detailJobId) : getShoeRepairJob(detailJobId)).then(r => r.data)
      : null,
    enabled: !!detailJobId,
  })

  // ── Mutations ─────────────────────────────────────────────────────────────
  const advanceMutation = useMutation({
    mutationFn: (vars: { id: string; status: string; note?: string }) =>
      mode === 'watch'
        ? updateJobStatus(vars.id, vars.status as JobStatus, vars.note)
        : updateShoeRepairJobStatus(vars.id, vars.status, vars.note),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      setStats(s => ({ ...s, advanced: s.advanced + 1 }))
      setDone(prev => new Set([...prev, vars.id]))
      resetPanel()
    },
  })

  const noteMutation = useMutation({
    mutationFn: (vars: { id: string; note: string }) =>
      mode === 'watch' ? addJobNote(vars.id, vars.note) : addShoeJobNote(vars.id, vars.note),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      if (cardState === 'noUpdate') {
        setStats(s => ({ ...s, checkedIn: s.checkedIn + 1 }))
        setDone(prev => new Set([...prev, vars.id]))
      }
      resetPanel()
    },
  })

  const claimMutation = useMutation<unknown, Error, { id: string; claim: boolean }>({
    mutationFn: (vars: { id: string; claim: boolean }) => {
      if (mode === 'watch') return vars.claim ? claimJob(vars.id) : releaseJob(vars.id)
      return vars.claim ? claimShoeJob(vars.id) : releaseShoeJob(vars.id)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] }),
  })

  // ── Handlers ──────────────────────────────────────────────────────────────
  function resetPanel() {
    setCardState('view')
    setSelectedNote('')
    setCustomNote('')
    setDragX(0)
    setSmsResult(null)
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
    noteMutation.mutate({ id: current.id, note: selectedNote || customNote || 'Checked in — no update' })
  }

  function handleSkip() {
    if (!currentId) return
    setQueueOrder(prev => prev ? [...prev.filter(id => id !== currentId), currentId] : prev)
    setStats(s => ({ ...s, skipped: s.skipped + 1 }))
    resetPanel()
  }

  function handleToggleClaim() {
    if (!currentId || !current) return
    claimMutation.mutate({ id: currentId, claim: !isMyClaim })
  }

  async function handleSendSms() {
    if (!current) return
    setSmsSending(true)
    setSmsResult(null)
    try {
      const event = current.status === 'awaiting_go_ahead' ? 'quote_sent' : 'job_ready'
      if (mode === 'watch') {
        await resendJobNotification(current.id, event as 'job_live' | 'job_ready' | 'quote_sent')
      } else {
        await resendShoeNotification(current.id, event)
      }
      setSmsResult('sent')
    } catch {
      setSmsResult('error')
    }
    setSmsSending(false)
  }

  // ── Swipe ─────────────────────────────────────────────────────────────────
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

  // ── Derived ───────────────────────────────────────────────────────────────
  const rotation = Math.min(Math.max(dragX / 18, -12), 12)
  const advanceHint = dragX > SWIPE_THRESHOLD * 0.4
  const skipHint = dragX < -SWIPE_THRESHOLD * 0.4
  const nextStatus = current ? STATUS_NEXT[current.status] : null
  const collectionUrgency = current ? getCollectionUrgency(current.collection_date) : 3
  const days = current ? daysInShop(current.created_at) : 0
  const isPending = advanceMutation.isPending || noteMutation.isPending || claimMutation.isPending

  const chipBase = 'px-3 py-1 rounded-full text-xs font-medium transition-all border'
  function chipStyle(active: boolean, ac = 'var(--cafe-gold)') {
    return { backgroundColor: active ? ac : 'rgba(31,23,18,0.06)', color: active ? '#fff' : 'var(--cafe-text-muted)', borderColor: active ? ac : 'var(--cafe-border)' }
  }

  // ── Loading ───────────────────────────────────────────────────────────────
  if (isLoading) return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(31,23,18,0.92)' }}>
      <Spinner />
    </div>
  )

  // ── Empty / done ──────────────────────────────────────────────────────────
  if (!current) return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ backgroundColor: 'rgba(31,23,18,0.97)' }}>
      <div className="rounded-2xl p-6 w-full max-w-sm" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
        <h2 className="text-xl font-bold mb-4 text-center" style={{ color: 'var(--cafe-text)', fontFamily: "'Playfair Display', Georgia, serif" }}>
          Queue Clear 👌
        </h2>
        {/* Session summary */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'Advanced', count: stats.advanced, color: 'var(--cafe-gold)' },
            { label: 'Checked In', count: stats.checkedIn, color: 'var(--cafe-text-muted)' },
            { label: 'Skipped', count: stats.skipped, color: 'var(--cafe-border-2)' },
          ].map(({ label, count, color }) => (
            <div key={label} className="text-center p-3 rounded-xl" style={{ backgroundColor: 'var(--cafe-bg)', border: '1px solid var(--cafe-border)' }}>
              <div className="text-2xl font-black" style={{ color }}>{count}</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{label}</div>
            </div>
          ))}
        </div>
        <button onClick={onClose} className="w-full py-2.5 rounded-xl font-semibold" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff' }}>
          Done
        </button>
      </div>
    </div>
  )

  // ── Job detail popup ──────────────────────────────────────────────────────
  if (detailJobId) {
    const detail = detailQuery.data
    const detailJob = jobMap[detailJobId]
    return (
      <div className="fixed inset-0 z-50 flex flex-col" style={{ backgroundColor: '#1F1712' }}>
        <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <span className="font-bold" style={{ color: '#FCFAF6', fontFamily: "'Playfair Display', Georgia, serif" }}>
            {detailJob?.job_number} — Details
          </span>
          <button onClick={() => setDetailJobId(null)} className="p-2" style={{ color: '#8A7563' }}><X size={20} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {detailQuery.isLoading ? (
            <div className="flex justify-center pt-8"><Spinner /></div>
          ) : detail ? (
            <div className="space-y-4 max-w-sm mx-auto">
              {/* Key info */}
              <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
                <div className="text-sm font-semibold mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Job Info</div>
                {detail.description && <p className="text-sm mb-2" style={{ color: 'var(--cafe-text)' }}>{detail.description}</p>}
                {detail.collection_date && (
                  <div className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>Collection: {detail.collection_date}</div>
                )}
                {detail.salesperson && (
                  <div className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>Salesperson: {detail.salesperson}</div>
                )}
              </div>

              {/* Shoe items */}
              {'items' in detail && (detail as ShoeRepairJob).items.length > 0 && (
                <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
                  <div className="text-sm font-semibold mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Repair Items</div>
                  <div className="space-y-1">
                    {(detail as ShoeRepairJob).items.map((item, i) => (
                      <div key={i} className="flex justify-between text-sm" style={{ color: 'var(--cafe-text)' }}>
                        <span>{item.item_name}</span>
                        {item.unit_price_cents != null && (
                          <span style={{ color: 'var(--cafe-text-muted)' }}>${(item.unit_price_cents / 100).toFixed(2)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Financials */}
              <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
                <div className="text-sm font-semibold mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Financials</div>
                <div className="flex justify-between text-sm" style={{ color: 'var(--cafe-text)' }}>
                  <span>Deposit</span><span>${(detail.deposit_cents / 100).toFixed(2)}</span>
                </div>
                {detail.cost_cents > 0 && (
                  <div className="flex justify-between text-sm mt-1" style={{ color: 'var(--cafe-text)' }}>
                    <span>Job total</span><span>${(detail.cost_cents / 100).toFixed(2)}</span>
                  </div>
                )}
              </div>

              {/* Open full page */}
              <Link
                to={mode === 'watch' ? `/jobs/${detailJobId}` : `/shoe-repairs/${detailJobId}`}
                onClick={onClose}
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-semibold"
                style={{ backgroundColor: 'rgba(184,149,86,0.12)', color: 'var(--cafe-gold-dark)', border: '1px solid rgba(184,149,86,0.25)' }}
              >
                <ExternalLink size={14} /> Open full job
              </Link>
            </div>
          ) : (
            <p className="text-center text-sm" style={{ color: 'var(--cafe-text-muted)' }}>Could not load details.</p>
          )}
        </div>
      </div>
    )
  }

  // ── Main ──────────────────────────────────────────────────────────────────
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(f => !f)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs"
            style={{ backgroundColor: filterCount > 0 ? 'rgba(184,149,86,0.2)' : 'rgba(255,255,255,0.06)', color: filterCount > 0 ? '#B89556' : '#8A7563', border: `1px solid ${filterCount > 0 ? 'rgba(184,149,86,0.4)' : 'rgba(255,255,255,0.1)'}` }}
          >
            <Filter size={12} />
            {filterCount > 0 ? `${filterCount} filter${filterCount > 1 ? 's' : ''}` : 'Filter'}
          </button>
          <button onClick={onClose} className="p-2" style={{ color: '#8A7563' }}><X size={20} /></button>
        </div>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="px-5 py-3 space-y-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', backgroundColor: 'rgba(255,255,255,0.03)' }}>
          <div>
            <div className="text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: 'rgba(255,255,255,0.35)' }}>Status</div>
            <div className="flex flex-wrap gap-1.5">
              {QUEUE_STATUSES.map(s => {
                const on = filterStatuses.has(s)
                return (
                  <button key={s} onClick={() => setFilterStatuses(prev => { const n = new Set(prev); on ? n.delete(s) : n.add(s); return n })}
                    className="px-2.5 py-1 rounded-full text-xs border"
                    style={{ backgroundColor: on ? 'var(--cafe-gold)' : 'rgba(255,255,255,0.06)', color: on ? '#fff' : '#8A7563', borderColor: on ? 'var(--cafe-gold)' : 'rgba(255,255,255,0.1)' }}>
                    {STATUS_LABELS[s] ?? s}
                  </button>
                )
              })}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: 'rgba(255,255,255,0.35)' }}>Priority</div>
            <div className="flex gap-1.5">
              {ALL_PRIORITIES.map(p => {
                const on = filterPriorities.has(p)
                return (
                  <button key={p} onClick={() => setFilterPriorities(prev => { const n = new Set(prev); on ? n.delete(p) : n.add(p); return n })}
                    className="px-2.5 py-1 rounded-full text-xs border capitalize"
                    style={{ backgroundColor: on ? PRIORITY_COLORS[p] : 'rgba(255,255,255,0.06)', color: on ? '#fff' : '#8A7563', borderColor: on ? PRIORITY_COLORS[p] : 'rgba(255,255,255,0.1)' }}>
                    {p}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setFilterDueToday(f => !f)}
              className="px-2.5 py-1 rounded-full text-xs border"
              style={{ backgroundColor: filterDueToday ? '#C0392B' : 'rgba(255,255,255,0.06)', color: filterDueToday ? '#fff' : '#8A7563', borderColor: filterDueToday ? '#C0392B' : 'rgba(255,255,255,0.1)' }}>
              Due today / overdue only
            </button>
            {filterCount > 0 && (
              <button onClick={() => { setFilterStatuses(new Set()); setFilterPriorities(new Set()); setFilterDueToday(false) }}
                className="text-xs" style={{ color: '#8A7563' }}>
                Clear all
              </button>
            )}
          </div>
        </div>
      )}

      {/* Progress bar */}
      {(doneCount + remaining) > 0 && (
        <div className="h-1" style={{ backgroundColor: 'rgba(184,149,86,0.15)' }}>
          <div className="h-full transition-all duration-300" style={{ width: `${(doneCount / (doneCount + remaining)) * 100}%`, backgroundColor: 'var(--cafe-gold)' }} />
        </div>
      )}

      {/* Card area */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-4 relative overflow-hidden">

        {/* Swipe hints */}
        {skipHint && cardState === 'view' && (
          <div className="absolute left-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(-12deg)', opacity: Math.min(1, Math.abs(dragX) / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-base" style={{ backgroundColor: '#3B2F27', color: '#D3C8BA', border: '2px solid #5F4D3E' }}>SKIP</span>
          </div>
        )}
        {advanceHint && cardState === 'view' && (
          <div className="absolute right-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(12deg)', opacity: Math.min(1, dragX / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-base" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff', border: '2px solid #D4AF5E' }}>ADVANCE</span>
          </div>
        )}

        {/* ── VIEW card ── */}
        {cardState === 'view' && (
          <div
            ref={cardRef}
            className="w-full max-w-sm rounded-2xl shadow-2xl"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', transform: `translateX(${dragX}px) rotate(${rotation}deg)`, transition: isDragging ? 'none' : 'transform 0.35s cubic-bezier(0.34,1.56,0.64,1)', touchAction: 'none', userSelect: 'none', cursor: isDragging ? 'grabbing' : 'grab' }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {/* Priority bar */}
            <div className="h-2 rounded-t-2xl flex overflow-hidden">
              <div className="flex-1" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#8A7563' }} />
              {isMyClaim && <div className="w-6" style={{ backgroundColor: 'var(--cafe-gold)' }} />}
            </div>

            <div className="p-5">
              {/* Job number — clickable for detail */}
              <div className="flex items-start justify-between mb-2">
                <div>
                  <button
                    onPointerDown={e => e.stopPropagation()}
                    onClick={() => setDetailJobId(current.id)}
                    className="text-3xl font-black tracking-tight flex items-center gap-1.5 group"
                    style={{ color: 'var(--cafe-espresso)', fontFamily: "'Playfair Display', Georgia, serif" }}
                  >
                    {current.job_number}
                    <ExternalLink size={14} className="opacity-0 group-hover:opacity-60 transition-opacity" style={{ color: 'var(--cafe-gold)' }} />
                  </button>
                  <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                    <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {days === 0 ? 'Today' : days === 1 ? '1 day in shop' : `${days} days in shop`}
                    </span>
                    {collectionUrgency === 0 && <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#7B241C', color: '#FADBD8' }}>OVERDUE</span>}
                    {collectionUrgency === 1 && <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#C0392B', color: '#fff' }}>DUE TODAY</span>}
                    {collectionUrgency === 2 && <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#D4693A', color: '#fff' }}>DUE TOMORROW</span>}
                    {isMyClaim && <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff' }}>ON IT</span>}
                    {isOthersClaim && <span className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>by {current.claimed_by_name ?? 'someone'}</span>}
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase text-white shrink-0" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#8A7563' }}>
                  {current.priority}
                </span>
              </div>

              <div className="text-lg font-semibold leading-snug mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.title}</div>
              {current.customer_name && <div className="text-sm mb-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.customer_name}</div>}

              {/* Context */}
              {current.type === 'shoe' && current.items && current.items.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {current.items.slice(0, 4).map((item, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>{item}</span>
                  ))}
                  {current.items.length > 4 && <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>+{current.items.length - 4}</span>}
                </div>
              )}
              {current.type === 'watch' && current.description && (
                <p className="text-xs mb-2 line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.description}</p>
              )}

              {RECOMMENDED_ACTION[current.status] && (
                <div className="flex items-center gap-1.5 mb-3 mt-1">
                  <ChevronRight size={13} style={{ color: 'var(--cafe-gold)', flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: 'var(--cafe-amber)' }}>{RECOMMENDED_ACTION[current.status]}</span>
                </div>
              )}

              {/* Status pills */}
              <div className="flex items-center gap-2 flex-wrap mb-3">
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

              {/* SMS reminder */}
              {SMS_REMIND_STATUSES.has(current.status) && (
                <div className="mb-3">
                  <button
                    onPointerDown={e => e.stopPropagation()}
                    onClick={handleSendSms}
                    disabled={smsSending || smsResult === 'sent'}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium w-full justify-center"
                    style={{ backgroundColor: smsResult === 'sent' ? 'rgba(184,149,86,0.12)' : 'var(--cafe-bg)', color: smsResult === 'sent' ? 'var(--cafe-gold-dark)' : 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}
                  >
                    <MessageSquare size={13} />
                    {smsSending ? 'Sending…' : smsResult === 'sent' ? 'SMS sent ✓' : smsResult === 'error' ? 'SMS failed — tap to retry' : current.status === 'awaiting_go_ahead' ? 'Remind customer (SMS)' : 'Notify ready (SMS)'}
                  </button>
                </div>
              )}

              {/* Card actions */}
              <div className="flex gap-2 pt-2" style={{ borderTop: '1px solid var(--cafe-border)' }}>
                <button onPointerDown={e => e.stopPropagation()} onClick={() => { setCardState('note'); setSelectedNote(''); setCustomNote('') }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>
                  <StickyNote size={13} /> Note
                </button>
                <button onPointerDown={e => e.stopPropagation()} onClick={handleToggleClaim}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{ backgroundColor: isMyClaim ? 'rgba(184,149,86,0.12)' : 'var(--cafe-bg)', color: isMyClaim ? 'var(--cafe-gold-dark)' : 'var(--cafe-text-muted)', border: `1px solid ${isMyClaim ? 'rgba(184,149,86,0.4)' : 'var(--cafe-border)'}` }}>
                  <Wrench size={13} /> {isMyClaim ? 'Release' : 'Claim'}
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
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-amber)' }}>Advance to: <strong>{STATUS_LABELS[nextStatus!] ?? nextStatus}</strong></div>
              {(ADVANCE_NOTE_CHIPS[nextStatus!] ?? []).length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Add a note (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {(ADVANCE_NOTE_CHIPS[nextStatus!] ?? []).map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }} className={chipBase} style={chipStyle(selectedNote === chip)}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Or type a custom note…" value={customNote} onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }} className="w-full px-3 py-2 rounded-lg text-sm mb-4" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleAdvance} disabled={isPending} className="flex-1 py-2.5 rounded-xl text-sm font-bold" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff', opacity: isPending ? 0.65 : 1 }}>{isPending ? 'Saving…' : 'Confirm'}</button>
              </div>
              {advanceMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed — try again.</p>}
            </div>
          </div>
        )}

        {/* ── NOTE panel ── */}
        {cardState === 'note' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: 'var(--cafe-espresso-3)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Add a note — status unchanged</div>
              {(STATUS_NOTE_CHIPS[current.status] ?? []).length > 0 && (
                <div className="mb-3">
                  <div className="flex flex-wrap gap-2">
                    {(STATUS_NOTE_CHIPS[current.status] ?? []).map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }} className={chipBase} style={chipStyle(selectedNote === chip, 'var(--cafe-espresso-3)')}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Type a note…" value={customNote} onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }} className="w-full px-3 py-2 rounded-lg text-sm mb-4" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleSaveNote} disabled={isPending || (!selectedNote && !customNote.trim())} className="flex-1 py-2.5 rounded-xl text-sm font-bold" style={{ backgroundColor: 'var(--cafe-espresso-2)', color: '#D5C8BB', opacity: isPending || (!selectedNote && !customNote.trim()) ? 0.5 : 1 }}>{isPending ? 'Saving…' : 'Save Note'}</button>
              </div>
              {noteMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed — try again.</p>}
            </div>
          </div>
        )}

        {/* ── NO UPDATE panel ── */}
        {cardState === 'noUpdate' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: 'var(--cafe-border-2)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Mark checked in — no update needed</div>
              {(NO_UPDATE_CHIPS[current.status] ?? []).length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Reason (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {(NO_UPDATE_CHIPS[current.status] ?? []).map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }} className={chipBase} style={chipStyle(selectedNote === chip, 'var(--cafe-text-muted)')}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Add a reason (optional)…" value={customNote} onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }} className="w-full px-3 py-2 rounded-lg text-sm mb-4" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleCheckedIn} disabled={isPending} className="flex-1 py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2" style={{ backgroundColor: 'var(--cafe-espresso)', color: '#D5C8BB', opacity: isPending ? 0.65 : 1 }}>
                  <CheckCheck size={15} />{isPending ? 'Saving…' : 'Checked In'}
                </button>
              </div>
              {noteMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed — try again.</p>}
            </div>
          </div>
        )}

        {cardState === 'view' && (
          <p className="mt-6 text-xs text-center select-none" style={{ color: 'rgba(184,149,86,0.3)' }}>
            <span>← skip</span>{'  ·  '}<span>advance →</span>
          </p>
        )}
      </div>

      {/* Bottom buttons */}
      {cardState === 'view' && (
        <div className="px-5 pb-8 pt-2 flex gap-3">
          <button onClick={handleSkip} className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#8A7563', border: '1px solid rgba(255,255,255,0.1)' }}>
            <SkipForward size={15} /> Skip
          </button>
          <button onClick={() => { setCardState('noUpdate'); setSelectedNote(''); setCustomNote('') }} className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#D5C8BB', border: '1px solid rgba(255,255,255,0.1)' }}>
            <CheckCheck size={15} /> No Update
          </button>
          <button onClick={() => setCardState('advance')} disabled={!nextStatus} className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: nextStatus ? 'var(--cafe-gold)' : 'rgba(255,255,255,0.05)', color: nextStatus ? '#fff' : 'rgba(255,255,255,0.2)', border: 'none' }}>
            <ChevronRight size={15} /> Advance
          </button>
        </div>
      )}
    </div>
  )
}
