import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, BarChart3, Calendar, CalendarDays, ChevronLeft, ChevronRight, Clock, CreditCard, GripVertical, LayoutGrid, List, Map as MapIcon, MapPin, Minus, Phone, Search, ShoppingCart, UserPlus, Users, X } from 'lucide-react'
import {
  createAutoKeyInvoiceFromQuote,
  createAutoKeyJob,
  createAutoKeyQuote,
  createCustomer,
  deleteAutoKeyJob,
  getApiErrorMessage,
  getAutoKeyJob,
  listCustomerAccounts,
  listAutoKeyInvoices,
  listAutoKeyJobs,
  listAutoKeyQuotes,
  listCustomers,
  listUsers,
  sendAutoKeyQuote,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  getAutoKeyQuoteSuggestions,
  searchVehicleKeySpecs,
  MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS,
  type VehicleKeySpecMatch,
  type AutoKeyJob,
  type Customer,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import MobileServicesMap from '@/components/MobileServicesMap'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
import { AddTechnicianModal, MobileCommissionRulesModal } from '@/components/MobileServicesTechnicianModals'
import { AklComplexityPill, parseAklComplexity } from '@/components/auto-key/AklComplexityPill'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import {
  KanbanBoard,
  JobCard as KanbanJobCard,
  AUTO_KEY_KANBAN_COLUMNS,
  findColumnForStatus,
} from '@/components/kanban'
import { useAutoKeyDayBeforeReminders } from '@/hooks/useAutoKeyDayBeforeReminders'
import { useAutoKeyReportData } from '@/hooks/useAutoKeyReportData'
import { useMobileServicesModals } from '@/hooks/useMobileServicesModals'
import { useWeekSchedulerDnD } from '@/hooks/useWeekSchedulerDnD'
import { AUTO_KEY_JOB_TYPES, MOBILE_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import {
  civilAddDays,
  civilMondayOfWeekContaining,
  hourMinuteInTimeZone,
  zonedWallTimeToUtcIso,
} from '@/lib/shopCalendarTime'
import { formatDate, STATUS_LABELS } from '@/lib/utils'

const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'quote_sent',
  'awaiting_booking_confirmation',
  'booking_confirmed',
  'job_delayed',
  'en_route',
  'on_site',
  'work_completed',
  'invoice_paid',
  'failed_job',
]

const AUTO_KEY_CLOSED_STATUSES = ['invoice_paid', 'failed_job'] as const
const AUTO_KEY_ACTIVE_STATUSES = [
  'awaiting_quote',
  'quote_sent',
  'awaiting_booking_confirmation',
  'booking_confirmed',
  'job_delayed',
  'en_route',
  'on_site',
  'work_completed',
] as const

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

function ymdLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function isYmd(value: string | null | undefined): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value)
}

function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

function dateFromYmdLocal(ymd: string): Date {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Reschedule onto target civil YYYY-MM-DD in shop calendar, keeping wall time in `shopTimeZone`, or 09:00 if unscheduled. */
function isoScheduledOnDayKeepingShopTime(
  jobId: string,
  targetDayYmd: string,
  jobs: Array<{ id: string; scheduled_at?: string }>,
  shopTimeZone: string,
): string {
  const job = jobs.find((j) => j.id === jobId)
  let hour = 9
  let minute = 0
  if (job?.scheduled_at) {
    const hm = hourMinuteInTimeZone(job.scheduled_at, shopTimeZone)
    hour = hm.hour
    minute = hm.minute
  }
  return zonedWallTimeToUtcIso(targetDayYmd, hour, minute, shopTimeZone)
}

/** Local hour rows for week grid: 7:00–21:00 slots (7am–9pm). */
const WEEK_SCHEDULE_HOURS = Array.from({ length: 15 }, (_, i) => 7 + i)
const WEEK_UNSCHEDULED_DROP_ID = 'week-unscheduled'
const WEEK_DAY_DROP_PREFIX = 'week-day:'
const WEEK_SLOT_DROP_PREFIX = 'week-slot:'

function weekDayDropId(dayStr: string) {
  return `${WEEK_DAY_DROP_PREFIX}${dayStr}`
}

function weekSlotDropId(dayStr: string, hour: number) {
  return `${WEEK_SLOT_DROP_PREFIX}${dayStr}:${hour}`
}

function weekSlotScheduledAt(dayStr: string, hour: number, shopTimeZone: string): string {
  return new Date(zonedWallTimeToUtcIso(dayStr, hour, 0, shopTimeZone)).toISOString()
}

function stopDragControlPropagation(event: { stopPropagation: () => void }) {
  event.stopPropagation()
}

interface WeekSchedulerJob {
  id: string
  job_number: string
  title: string
  scheduled_at?: string
  customer_id?: string
  customer_name?: string | null
  customer_phone?: string | null
  assigned_user_id?: string
  status?: JobStatus
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  key_type?: string
  key_quantity?: number
  job_type?: string
  job_address?: string
  tech_notes?: string
}

function weekJobVehicleSummary(job: WeekSchedulerJob) {
  const vehicle = [job.vehicle_year, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')
  return [vehicle || undefined, job.registration_plate || undefined].filter(Boolean).join(' · ') || undefined
}

function weekJobSecondarySummary(job: WeekSchedulerJob, customerName?: string, assignedTechName?: string) {
  const bits = [
    customerName,
    job.job_type || undefined,
    assignedTechName ? `Tech: ${assignedTechName}` : undefined,
  ].filter(Boolean)
  return bits.length ? bits.join(' · ') : undefined
}

/** Monday–Sunday week in local time containing YYYY-MM-DD anchor */
function weekRangeFromYmd(ymd: string): { date_from: string; date_to: string } {
  const anchor = dateFromYmdLocal(ymd)
  const day = anchor.getDay()
  const diff = anchor.getDate() - day + (day === 0 ? -6 : 1)
  const mon = new Date(anchor)
  mon.setDate(diff)
  const sun = new Date(mon)
  sun.setDate(mon.getDate() + 6)
  return { date_from: ymdLocal(mon), date_to: ymdLocal(sun) }
}

function monthRangeFromYmd(ymd: string): { date_from: string; date_to: string } {
  const [y, m] = ymd.split('-').map(Number)
  const pad = (n: number) => String(n).padStart(2, '0')
  const start = `${y}-${pad(m)}-01`
  const last = new Date(y, m, 0)
  const end = `${y}-${pad(m)}-${pad(last.getDate())}`
  return { date_from: start, date_to: end }
}

function nextMobileStatus(status: JobStatus): JobStatus | null {
  if (status === 'awaiting_quote') return 'quote_sent'
  if (status === 'quote_sent') return 'awaiting_booking_confirmation'
  if (status === 'awaiting_booking_confirmation') return 'booking_confirmed'
  if (status === 'booking_confirmed') return 'en_route'
  if (status === 'en_route') return 'on_site'
  if (status === 'on_site') return 'work_completed'
  return null
}

function PlannerJobDetailModal({
  jobId,
  onClose,
  customers,
  users,
}: {
  jobId: string
  onClose: () => void
  customers: Customer[]
  users: { id: string; full_name: string }[]
}) {
  const { data: job, isLoading, isError, error } = useQuery({
    queryKey: ['auto-key-jobs', jobId, 'planner-detail'],
    queryFn: () => getAutoKeyJob(jobId).then(r => r.data),
    enabled: !!jobId,
  })
  const customer = job ? customers.find(c => c.id === job.customer_id) : undefined
  const tech = job?.assigned_user_id ? users.find(u => u.id === job.assigned_user_id) : undefined
  const j = job as AutoKeyJob | undefined

  const row = (label: string, value: string | ReactNode) => (
    <>
      <dt className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{label}</dt>
      <dd className="text-sm" style={{ color: 'var(--ms-text)' }}>{value}</dd>
    </>
  )

  return (
    <Modal title={j ? `Job #${j.job_number}` : 'Job details'} onClose={onClose}>
      {isLoading && <Spinner />}
      {isError && <p className="text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(error, 'Could not load job')}</p>}
      {j && (
        <div className="space-y-4">
          <p className="text-base font-medium" style={{ color: 'var(--ms-text)' }}>{j.title}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
            <dl className="contents">
              {row('Status', <Badge status={j.status} />)}
              {row('Customer', customer?.full_name ?? '—')}
              {row('Phone', customer?.phone ?? '—')}
              {row('Assigned tech', tech?.full_name ?? '—')}
              {row('Job type', j.job_type ?? '—')}
              {row('Vehicle', [j.vehicle_make, j.vehicle_model, j.vehicle_year, j.registration_plate].filter(Boolean).join(' · ') || '—')}
              {row('Address', j.job_address ?? '—')}
              {row('Scheduled', j.scheduled_at ? new Date(j.scheduled_at).toLocaleString() : '—')}
              {row('Priority', j.priority)}
              {row('Deposit', formatCents(j.deposit_cents))}
              {row('Cost / quote', formatCents(j.cost_cents))}
              {row('Key type', j.key_type ?? '—')}
              {row('Blade / chip', [j.blade_code, j.chip_type].filter(Boolean).join(' · ') || '—')}
            </dl>
          </div>
          {j.additional_services_json && (() => {
              try {
                const arr = JSON.parse(j.additional_services_json) as { preset?: string | null; custom?: string | null }[]
                if (!Array.isArray(arr) || arr.length === 0) return null
                const lines = arr.map(x => x.custom || x.preset).filter(Boolean)
                if (!lines.length) return null
                return (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Additional services</p>
                    <ul className="text-sm list-disc pl-5 space-y-0.5" style={{ color: 'var(--ms-text)' }}>
                      {lines.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                )
              } catch {
                return null
              }
            })()}
          {j.description && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Description</p>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--ms-text)' }}>{j.description}</p>
            </div>
          )}
          {j.tech_notes && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Tech notes</p>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--ms-text)' }}>{j.tech_notes}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button variant="secondary" type="button" onClick={onClose}>Close</Button>
            <Link
              to={`/auto-key/${j.id}`}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
            >
              Open full job page
            </Link>
          </div>
        </div>
      )}
    </Modal>
  )
}

function CustomerSearchSelect({ customers, value, onChange }: { customers: Customer[]; value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const q = search.trim().toLowerCase()
  const filtered = q
    ? customers.filter(c =>
        c.full_name.toLowerCase().includes(q) ||
        (c.phone && c.phone.replace(/\D/g, '').includes(q.replace(/\D/g, ''))) ||
        (c.email && c.email.toLowerCase().includes(q))
      )
    : customers
  const selected = customers.find(c => c.id === value)
  const display = selected ? `${selected.full_name}${selected.phone ? ` · ${selected.phone}` : ''}` : search
  const safeHighlight = filtered.length === 0 ? 0 : Math.min(highlight, filtered.length - 1)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const h = (e: MouseEvent) => { if (!el.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={containerRef} className="relative">
      <Input
        label="Search customer"
        value={open ? search : display}
        onChange={e => { setSearch(e.target.value); setOpen(true); setHighlight(0) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={e => {
          if (!open || filtered.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(i => (i + 1) % filtered.length) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(i => (i - 1 + filtered.length) % filtered.length) }
          else if (e.key === 'Enter') { e.preventDefault(); onChange(filtered[safeHighlight].id); setOpen(false); setSearch('') }
          else if (e.key === 'Escape') setOpen(false)
        }}
        placeholder="Type name, phone or email…"
      />
      {open && (
        <ul className="absolute z-50 w-full mt-1 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-48" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)' }}>
          {filtered.slice(0, 30).map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm truncate"
                style={{ color: 'var(--ms-text)', backgroundColor: i === safeHighlight ? '#F5EDE0' : 'transparent' }}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={e => { e.preventDefault(); onChange(c.id); setOpen(false); setSearch('') }}
              >
                {c.full_name}{c.phone ? ` · ${c.phone}` : ''}{c.email ? ` · ${c.email}` : ''}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-3 py-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No customers match</li>}
        </ul>
      )}
    </div>
  )
}

function NewAutoKeyJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { hasFeature } = useAuth()
  const [error, setError] = useState('')
  const [step, setStep] = useState<1 | 2>(1)
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
  const [applySuggestedQuote, setApplySuggestedQuote] = useState(true)
  const [sendBookingSms, setSendBookingSms] = useState(false)
  const [extraServices, setExtraServices] = useState<Array<{ preset: string; custom: string }>>([])
  const [form, setForm] = useState({
    customer_id: '',
    customer_account_id: '',
    assigned_user_id: '',
    description: '',
    job_type: '' as string,
    job_address: '',
    scheduled_at: '',
    vehicle_make: '',
    vehicle_model: '',
    vehicle_year: '',
    registration_plate: '',
    vin: '',
    key_type: '',
    blade_code: '',
    chip_type: '',
    tech_notes: '',
    key_quantity: '1',
    priority: 'normal' as 'low' | 'normal' | 'high' | 'urgent',
    status: 'awaiting_quote' as JobStatus,
    salesperson: '',
    deposit: '',
    cost: '',
    commission_lead_source: 'shop_referred',
  })

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const customerFirstName = useMemo(() => {
    const raw =
      customerMode === 'new'
        ? newCustomer.full_name
        : (customers.find(c => c.id === form.customer_id)?.full_name ?? '')
    return (raw || '').trim().split(/\s+/)[0] ?? ''
  }, [customerMode, newCustomer.full_name, form.customer_id, customers])

  const autoTitle = useMemo(() => {
    const make = form.vehicle_make.trim()
    const model = form.vehicle_model.trim()
    const yearStr = form.vehicle_year.trim()
    const car = [make, yearStr, model].filter(Boolean).join(' ')
    if (!customerFirstName) return car || 'New job'
    return car ? `${customerFirstName} - ${car}` : `${customerFirstName} - Job`
  }, [customerFirstName, form.vehicle_make, form.vehicle_year, form.vehicle_model])

  const suggestionQty = Math.max(1, Number.parseInt(form.key_quantity, 10) || 1)
  const pricingTier = form.customer_account_id ? 'b2b' : 'retail'
  const { data: quoteSuggestion, isFetching: quoteSuggestionLoading } = useQuery({
    queryKey: ['auto-key-quote-suggestions', form.job_type, suggestionQty, pricingTier],
    queryFn: () =>
      getAutoKeyQuoteSuggestions({
        job_type: form.job_type.trim() || undefined,
        key_quantity: suggestionQty,
        pricing_tier: pricingTier,
      }).then(r => r.data),
  })

  useEffect(() => {
    if (!applySuggestedQuote || !quoteSuggestion) return
    const dollars = (quoteSuggestion.total_cents / 100).toFixed(2)
    setForm(f => ({ ...f, cost: dollars }))
  }, [applySuggestedQuote, quoteSuggestion?.total_cents])

  const yearNum = form.vehicle_year.trim() ? Number.parseInt(form.vehicle_year, 10) : undefined
  const { data: specSearch } = useQuery({
    queryKey: ['vehicle-key-specs', form.vehicle_make, form.vehicle_model, form.vehicle_year],
    queryFn: () =>
      searchVehicleKeySpecs({
        make: form.vehicle_make,
        model: form.vehicle_model,
        year: Number.isFinite(yearNum) ? yearNum : undefined,
      }).then(r => r.data),
    enabled:
      hasFeature('auto_key') &&
      (form.vehicle_make.trim().length >= 2 || form.vehicle_model.trim().length >= 2),
    staleTime: 60_000,
  })

  const applyVehicleSpec = (m: VehicleKeySpecMatch) => {
    setForm(f => ({
      ...f,
      vehicle_make: m.vehicle_make,
      vehicle_model: m.vehicle_model,
      vehicle_year: f.vehicle_year.trim() || (m.year_from != null ? String(m.year_from) : ''),
      key_type: m.key_type || f.key_type,
      chip_type: m.chip_type || f.chip_type,
      tech_notes: m.tech_notes || f.tech_notes,
      blade_code: m.suggested_blade_code || f.blade_code,
    }))
  }

  // ── Last job vehicle suggestion ─────────────────────────────────────────────
  const [lastJobDismissed, setLastJobDismissed] = useState(false)
  useEffect(() => { setLastJobDismissed(false) }, [form.customer_id])

  const { data: customerLastJob } = useQuery({
    queryKey: ['auto-key-last-job', form.customer_id],
    queryFn: () =>
      listAutoKeyJobs({ customer_id: form.customer_id, limit: 1 }).then(r => r.data[0] ?? null),
    enabled: customerMode === 'existing' && !!form.customer_id,
    staleTime: 30_000,
  })

  const lastJobHasVehicle = !!(customerLastJob?.vehicle_make || customerLastJob?.vehicle_model)
  const showLastJobBanner =
    customerMode === 'existing' &&
    !lastJobDismissed &&
    lastJobHasVehicle &&
    !form.vehicle_make.trim() &&
    !form.vehicle_model.trim()

  const applyLastJobVehicle = () => {
    if (!customerLastJob) return
    setForm(f => ({
      ...f,
      vehicle_make: customerLastJob.vehicle_make || f.vehicle_make,
      vehicle_model: customerLastJob.vehicle_model || f.vehicle_model,
      vehicle_year: customerLastJob.vehicle_year ? String(customerLastJob.vehicle_year) : f.vehicle_year,
      registration_plate: customerLastJob.registration_plate || f.registration_plate,
      vin: customerLastJob.vin || f.vin,
      key_type: customerLastJob.key_type || f.key_type,
      blade_code: customerLastJob.blade_code || f.blade_code,
      chip_type: customerLastJob.chip_type || f.chip_type,
      tech_notes: customerLastJob.tech_notes || f.tech_notes,
    }))
    setLastJobDismissed(true)
  }

  const matchingAccounts = form.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(form.customer_id))
    : customerAccounts

  const createMut = useMutation({
    mutationFn: async () => {
      if (!autoTitle.trim()) throw new Error('Job title could not be built — select or add a customer.')
      if (MOBILE_JOB_TYPES.has(form.job_type) && !form.job_address.trim()) {
        throw new Error('Address required for mobile jobs')
      }
      let customerId = form.customer_id
      if (customerMode === 'new') {
        if (!newCustomer.full_name.trim()) throw new Error('Customer name is required.')
        const { data } = await createCustomer(newCustomer)
        customerId = data.id
        qc.invalidateQueries({ queryKey: ['customers'] })
      } else if (!customerId) {
        throw new Error('Please select a customer.')
      }
      const customerPhone =
        customerMode === 'new'
          ? newCustomer.phone
          : customers.find(c => c.id === customerId)?.phone
      if (sendBookingSms) {
        if (!(customerPhone && customerPhone.trim())) {
          throw new Error('Customer mobile number is required to send a booking confirmation SMS.')
        }
        if (!form.scheduled_at.trim()) {
          throw new Error('Scheduled date & time is required when texting the customer to confirm booking.')
        }
      }
      const additional_services = extraServices
        .map(r => ({
          preset: r.preset.trim() || undefined,
          custom: r.custom.trim() || undefined,
        }))
        .filter(r => r.preset || r.custom)
      return createAutoKeyJob({
        customer_id: customerId,
        customer_account_id: form.customer_account_id || undefined,
        assigned_user_id: form.assigned_user_id || undefined,
        title: autoTitle.trim(),
        description: form.description.trim() || undefined,
        job_type: form.job_type || undefined,
        job_address: form.job_address.trim() || undefined,
        scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
        vehicle_make: form.vehicle_make.trim() || undefined,
        vehicle_model: form.vehicle_model.trim() || undefined,
        vehicle_year: form.vehicle_year ? Number(form.vehicle_year) : undefined,
        registration_plate: form.registration_plate.trim() || undefined,
        vin: form.vin.trim() || undefined,
        key_type: form.key_type.trim() || undefined,
        blade_code: form.blade_code.trim() || undefined,
        chip_type: form.chip_type.trim() || undefined,
        tech_notes: form.tech_notes.trim() || undefined,
        key_quantity: Math.max(1, Number(form.key_quantity || '1')),
        programming_status: 'not_required',
        priority: form.priority,
        status: form.status,
        salesperson: form.salesperson.trim() || undefined,
        deposit_cents: form.deposit ? Math.round(parseFloat(form.deposit) * 100) : 0,
        cost_cents: form.cost ? Math.round(parseFloat(form.cost) * 100) : 0,
        apply_suggested_quote: applySuggestedQuote,
        send_booking_sms: sendBookingSms,
        additional_services: additional_services.length ? additional_services : undefined,
        commission_lead_source: form.commission_lead_source || 'shop_referred',
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create Mobile Services job.')),
  })

  return (
    <Modal title="New Mobile Services Job" onClose={onClose} size="wide">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex items-center gap-1.5">
          <span
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            style={step === 1
              ? { backgroundColor: 'var(--ms-accent)', color: '#fff' }
              : { backgroundColor: 'var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
          >1</span>
          <span className="text-xs font-medium" style={{ color: step === 1 ? 'var(--ms-text)' : 'var(--ms-text-muted)' }}>
            Customer &amp; Vehicle
          </span>
        </div>
        <div className="flex-1 h-px mx-1" style={{ backgroundColor: 'var(--ms-border-strong)' }} />
        <div className="flex items-center gap-1.5">
          <span
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            style={step === 2
              ? { backgroundColor: 'var(--ms-accent)', color: '#fff' }
              : { backgroundColor: 'var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
          >2</span>
          <span className="text-xs font-medium" style={{ color: step === 2 ? 'var(--ms-text)' : 'var(--ms-text-muted)' }}>
            Schedule &amp; Details
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {/* ── STEP 1: Customer & Vehicle ── */}
        {step === 1 && (
          <>
            <div className="flex gap-2 mb-1">
              <button
                onClick={() => setCustomerMode('existing')}
                className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
                style={customerMode === 'existing' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}
              >Existing Customer</button>
              <button
                onClick={() => setCustomerMode('new')}
                className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
                style={customerMode === 'new' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}
              >New Customer</button>
            </div>
            {customerMode === 'existing' ? (
              <CustomerSearchSelect customers={customers} value={form.customer_id} onChange={id => setForm(f => ({ ...f, customer_id: id }))} />
            ) : (
              <>
                <Input label="Full Name *" value={newCustomer.full_name} onChange={e => setNewCustomer(f => ({ ...f, full_name: e.target.value }))} placeholder="Jane Smith" />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Input label="Phone" value={newCustomer.phone} onChange={e => setNewCustomer(f => ({ ...f, phone: e.target.value }))} placeholder="0412 345 678" />
                  <Input label="Email" type="email" value={newCustomer.email} onChange={e => setNewCustomer(f => ({ ...f, email: e.target.value }))} placeholder="jane@example.com" />
                </div>
                <Input label="Address" value={newCustomer.address} onChange={e => setNewCustomer(f => ({ ...f, address: e.target.value }))} placeholder="Optional" />
                <Textarea label="Notes" value={newCustomer.notes} onChange={e => setNewCustomer(f => ({ ...f, notes: e.target.value }))} rows={1} placeholder="Optional" />
              </>
            )}
            {customerMode === 'existing' && form.customer_id && matchingAccounts.length > 0 && (
              <Select label="Customer Account (optional)" value={form.customer_account_id} onChange={e => setForm(f => ({ ...f, customer_account_id: e.target.value }))}>
                <option value="">No B2B account</option>
                {matchingAccounts.map((account: CustomerAccount) => (
                  <option key={account.id} value={account.id}>
                    {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                  </option>
                ))}
              </Select>
            )}
            {/* Last job vehicle suggestion banner */}
            {showLastJobBanner && customerLastJob && (
              <div
                className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-sm"
                style={{ borderColor: 'var(--ms-accent)', backgroundColor: 'rgba(201,162,72,0.08)' }}
              >
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide mb-0.5" style={{ color: 'var(--ms-accent)' }}>
                    Last visit vehicle on file
                  </p>
                  <p className="truncate" style={{ color: 'var(--ms-text)' }}>
                    {[customerLastJob.vehicle_make, customerLastJob.vehicle_year, customerLastJob.vehicle_model]
                      .filter(Boolean).join(' ')}
                    {customerLastJob.registration_plate ? ` · ${customerLastJob.registration_plate}` : ''}
                    {customerLastJob.key_type ? ` · ${customerLastJob.key_type}` : ''}
                  </p>
                </div>
                <div className="flex gap-1.5 shrink-0">
                  <Button variant="ghost" onClick={() => setLastJobDismissed(true)}>Skip</Button>
                  <Button variant="primary" onClick={applyLastJobVehicle}>Use this</Button>
                </div>
              </div>
            )}

            <Select label="Primary job type" value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}>
              <option value="">Not set</option>
              {AUTO_KEY_JOB_TYPES.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </Select>
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Additional services (optional)</p>
              {extraServices.map((row, idx) => (
                <div key={idx} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2 items-end">
                  <Select
                    label={idx === 0 ? 'Preset type' : ''}
                    value={row.preset}
                    onChange={e => {
                      const v = e.target.value
                      setExtraServices(xs => xs.map((r, i) => (i === idx ? { ...r, preset: v } : r)))
                    }}
                  >
                    <option value="">— Choose type —</option>
                    {AUTO_KEY_JOB_TYPES.map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </Select>
                  <Input
                    label={idx === 0 ? 'Or custom note' : ''}
                    value={row.custom}
                    onChange={e => setExtraServices(xs => xs.map((r, i) => (i === idx ? { ...r, custom: e.target.value } : r)))}
                    placeholder="Custom work…"
                  />
                  <Button type="button" variant="ghost" className="shrink-0" aria-label="Remove line" onClick={() => setExtraServices(xs => xs.filter((_, i) => i !== idx))}>
                    <Minus size={18} />
                  </Button>
                </div>
              ))}
              <Button type="button" variant="secondary" onClick={() => setExtraServices(xs => [...xs, { preset: '', custom: '' }])}>
                Add another service line
              </Button>
            </div>
            <Input
              label={MOBILE_JOB_TYPES.has(form.job_type) ? 'Job address *' : 'Job address'}
              value={form.job_address}
              onChange={e => setForm(f => ({ ...f, job_address: e.target.value }))}
              placeholder={MOBILE_JOB_TYPES.has(form.job_type) ? 'Where to meet customer (required for mobile jobs)' : 'Where to meet customer (optional)'}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Vehicle make" value={form.vehicle_make} onChange={e => setForm(f => ({ ...f, vehicle_make: e.target.value }))} placeholder="e.g. Toyota" />
              <Input label="Vehicle model" value={form.vehicle_model} onChange={e => setForm(f => ({ ...f, vehicle_model: e.target.value }))} placeholder="e.g. Hilux" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Vehicle year" type="number" value={form.vehicle_year} onChange={e => setForm(f => ({ ...f, vehicle_year: e.target.value }))} placeholder="Filters database matches" />
              <Input
                label="Registration (reference only)"
                value={form.registration_plate}
                onChange={e => setForm(f => ({ ...f, registration_plate: e.target.value }))}
                placeholder="e.g. ABC123"
              />
            </div>
            {specSearch && specSearch.matches.length > 0 && (
              <div
                className="rounded-lg border p-2 text-sm"
                style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)' }}
              >
                <p className="font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>
                  Vehicle database — tap a row to fill key details
                </p>
                <ul className="max-h-48 overflow-y-auto space-y-1">
                  {specSearch.matches.map((m, i) => (
                    <li key={`${m.label}-${i}`}>
                      <button
                        type="button"
                        className="w-full text-left px-2 py-1.5 rounded transition"
                        style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
                        onMouseEnter={e => { e.currentTarget.style.opacity = '0.92' }}
                        onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
                        onClick={() => applyVehicleSpec(m)}
                      >
                        <span className="block">{m.label}</span>
                        {(m.suggested_blade_code || (m.key_blanks && m.key_blanks.length > 0)) && (
                          <span className="block text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                            Blanks: {(m.key_blanks ?? []).slice(0, 4).map(b => b.primary_code || b.blank_reference).filter(Boolean).join(', ') || m.suggested_blade_code}
                          </span>
                        )}
                        <div className="flex flex-wrap gap-1 mt-1">
                          {m.akl_complexity && <AklComplexityPill complexity={m.akl_complexity} />}
                          {m.bsu_required && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(201,162,72,0.15)', color: '#9A7220' }}>BSU required</span>}
                          {m.pin_required && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(201,106,90,0.12)', color: '#C96A5A' }}>PIN required</span>}
                          {m.dealer_required && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(201,106,90,0.2)', color: '#C96A5A' }}>Dealer only</span>}
                          {m.eeprom_required && !m.obd_programmable && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(120,100,180,0.15)', color: '#7060B0' }}>EEPROM</span>}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="VIN" value={form.vin} onChange={e => setForm(f => ({ ...f, vin: e.target.value }))} />
              <Input label="Key type" value={form.key_type} onChange={e => setForm(f => ({ ...f, key_type: e.target.value }))} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Blade / blank ref." value={form.blade_code} onChange={e => setForm(f => ({ ...f, blade_code: e.target.value }))} />
              <Input label="Chip / transponder" value={form.chip_type} onChange={e => setForm(f => ({ ...f, chip_type: e.target.value }))} />
            </div>
            <Input label="Qty" type="number" min="1" value={form.key_quantity} onChange={e => setForm(f => ({ ...f, key_quantity: e.target.value }))} />
          </>
        )}

        {/* ── STEP 2: Schedule & Details ── */}
        {step === 2 && (
          <>
            <Input label="Job title (auto-generated)" value={autoTitle} readOnly className="opacity-90" />
            <Select label="Assign tech" value={form.assigned_user_id} onChange={e => setForm(f => ({ ...f, assigned_user_id: e.target.value }))}>
              <option value="">Unassigned</option>
              {users.map((u: { id: string; full_name: string }) => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
            </Select>
            <Select
              label="Job source (commission tier)"
              value={form.commission_lead_source}
              onChange={e => setForm(f => ({ ...f, commission_lead_source: e.target.value }))}
            >
              {MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
            <Input
              label={sendBookingSms ? 'Scheduled (date & time) *' : 'Scheduled (date & time, optional)'}
              type="datetime-local"
              value={form.scheduled_at}
              onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))}
            />
            {sendBookingSms && (
              <p className="text-xs -mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                The customer receives a text with job summary, quote total, and time. Status will be set to "Awaiting booking confirm" until they tap confirm.
              </p>
            )}
            <Textarea label="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} />
            <Textarea
              label="Workshop / tech notes"
              value={form.tech_notes}
              onChange={e => setForm(f => ({ ...f, tech_notes: e.target.value }))}
              rows={3}
              placeholder="Immobiliser notes, EEPROM warnings, etc."
            />
            <div
              className="rounded-lg border p-3 space-y-2"
              style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)' }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
                Quote &amp; booking SMS
              </p>
              <label className="flex items-start gap-2 cursor-pointer text-sm" style={{ color: 'var(--ms-text)' }}>
                <input
                  type="checkbox"
                  className="mt-1 rounded"
                  checked={applySuggestedQuote}
                  onChange={e => setApplySuggestedQuote(e.target.checked)}
                />
                <span>
                  <span className="font-medium">Apply suggested quote</span>
                  <span className="block text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    Draft quote from job type and qty (inc. GST). Fills cost below when checked.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 cursor-pointer text-sm" style={{ color: 'var(--ms-text)' }}>
                <input
                  type="checkbox"
                  className="mt-1 rounded"
                  checked={sendBookingSms}
                  onChange={e => {
                    setSendBookingSms(e.target.checked)
                    if (e.target.checked) setApplySuggestedQuote(true)
                  }}
                />
                <span>
                  <span className="font-medium">Text customer to confirm booking</span>
                  <span className="block text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    Sends SMS with link to confirm. Requires customer mobile and scheduled time above.
                  </span>
                </span>
              </label>
              {quoteSuggestion && (
                <div className="text-sm pt-1 space-y-1" style={{ color: 'var(--ms-text)' }}>
                  <div className="flex justify-between gap-2">
                    <span style={{ color: 'var(--ms-text-muted)' }}>Suggested total (incl. GST)</span>
                    <span className="font-semibold tabular-nums">{formatCents(quoteSuggestion.total_cents)}</span>
                  </div>
                  {quoteSuggestionLoading && (
                    <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Updating…</p>
                  )}
                  <ul className="text-xs space-y-0.5 mt-1 max-h-24 overflow-y-auto" style={{ color: 'var(--ms-text-muted)' }}>
                    {quoteSuggestion.line_items.map((li, i) => (
                      <li key={i}>
                        {li.quantity}× {li.description} — {formatCents(li.unit_price_cents * li.quantity)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Select label="Priority" value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value as 'low' | 'normal' | 'high' | 'urgent' }))}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </Select>
              <Select label="Status" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value as JobStatus }))} disabled={sendBookingSms}>
                {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>)}
              </Select>
            </div>
            {sendBookingSms && (
              <p className="text-xs -mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                Initial status is forced to awaiting confirmation while the SMS link is open.
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Deposit ($)" type="number" step="0.01" value={form.deposit} onChange={e => setForm(f => ({ ...f, deposit: e.target.value }))} />
              <Input label="Cost ($)" type="number" step="0.01" value={form.cost} onChange={e => setForm(f => ({ ...f, cost: e.target.value }))} />
            </div>
            <Input label="Salesperson" value={form.salesperson} onChange={e => setForm(f => ({ ...f, salesperson: e.target.value }))} />
          </>
        )}

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex gap-2 pt-2">
          {step === 1 ? (
            <>
              <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
              <Button className="flex-1" type="button" onClick={() => { setError(''); setStep(2) }}>Next →</Button>
            </>
          ) : (
            <>
              <Button variant="secondary" className="flex-1" type="button" onClick={() => { setError(''); setStep(1) }}>← Back</Button>
              <Button className="flex-1" onClick={() => createMut.mutate()} disabled={createMut.isPending}>
                {createMut.isPending ? 'Creating…' : 'Create Job'}
              </Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}

const POS_QUICK_ITEMS = [
  // Key cutting & blanks
  { label: 'Key cut – basic', desc: 'Basic key cutting', price: 3500 },
  { label: 'Key cut – laser', desc: 'Laser-cut key', price: 12000 },
  { label: 'Key cut – Tibbe', desc: 'Tibbe key cutting', price: 15000 },
  { label: 'Blank – transponder', desc: 'Transponder blank', price: 4500 },
  { label: 'Blank – flip key', desc: 'Flip/smart key blank', price: 8500 },
  { label: 'Blank – proximity', desc: 'Proximity key blank', price: 12000 },
  // Programming
  { label: 'Program – transponder', desc: 'Transponder key programming', price: 9500 },
  { label: 'Program – proximity', desc: 'Proximity key programming', price: 15000 },
  { label: 'Program – all keys lost', desc: 'All keys lost – full programming', price: 25000 },
  { label: 'Program – add key', desc: 'Add key to existing', price: 7500 },
  { label: 'Sync remote', desc: 'Remote/fob sync', price: 5500 },
  // Duplication & replacement
  { label: 'Duplicate – transponder', desc: 'Duplicate transponder key', price: 12000 },
  { label: 'Duplicate – flip key', desc: 'Duplicate flip key', price: 18000 },
  { label: 'Replace – lost key', desc: 'Replace lost key (cut + program)', price: 15000 },
  { label: 'Replace – all keys lost', desc: 'Replace all lost keys', price: 35000 },
  // Lockout & entry
  { label: 'Lockout – car', desc: 'Car lockout / emergency entry', price: 12000 },
  { label: 'Lockout – boot/trunk', desc: 'Boot/trunk lockout', price: 8500 },
  { label: 'Lockout – roadside', desc: 'Roadside lockout callout', price: 18000 },
  // Ignition & lock work
  { label: 'Ignition repair', desc: 'Ignition barrel repair', price: 15000 },
  { label: 'Ignition replace', desc: 'Ignition barrel replacement', price: 25000 },
  { label: 'Broken key extraction', desc: 'Extract broken key from lock', price: 8500 },
  { label: 'Door lock change', desc: 'Door lock cylinder change', price: 12000 },
  { label: 'Boot lock change', desc: 'Boot/trunk lock change', price: 9500 },
  // Service & misc
  { label: 'Service call', desc: 'Service call / travel fee', price: 5500 },
  { label: 'After hours', desc: 'After-hours surcharge', price: 3500 },
  { label: 'Diagnostic', desc: 'Key/ECU diagnostic', price: 6500 },
] as const

interface CartLine {
  id: string
  description: string
  quantity: number
  unit_price_cents: number
}

function POSView({ customers, customerAccounts, onComplete }: { customers: Customer[]; customerAccounts: CustomerAccount[]; onComplete: () => void }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [customerId, setCustomerId] = useState('')
  const [customerAccountId, setCustomerAccountId] = useState('')
  const [linkToJobId, setLinkToJobId] = useState('')
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '' })
  const [cart, setCart] = useState<CartLine[]>([])

  const { data: activeJobsForCustomer = [] } = useQuery({
    queryKey: ['auto-key-jobs', 'active', customerId],
    queryFn: () => listAutoKeyJobs({ customer_id: customerId, active_only: true }).then(r => r.data),
    enabled: !!customerId && customerMode === 'existing',
  })
  const [customDesc, setCustomDesc] = useState('')
  const [customPrice, setCustomPrice] = useState('')
  const [error, setError] = useState('')
  const [successJobId, setSuccessJobId] = useState<string | null>(null)

  const subtotal = cart.reduce((s, l) => s + l.quantity * l.unit_price_cents, 0)
  const tax = 0
  const total = subtotal + tax

  const addToCart = (description: string, unit_price_cents: number, quantity = 1) => {
    const existing = cart.find(l => l.description === description && l.unit_price_cents === unit_price_cents)
    if (existing) {
      setCart(cart.map(l => l.id === existing.id ? { ...l, quantity: l.quantity + quantity } : l))
    } else {
      setCart([...cart, { id: crypto.randomUUID(), description, quantity, unit_price_cents }])
    }
  }

  const removeFromCart = (id: string) => setCart(cart.filter(l => l.id !== id))
  const updateQty = (id: string, qty: number) => {
    if (qty < 1) removeFromCart(id)
    else setCart(cart.map(l => l.id === id ? { ...l, quantity: qty } : l))
  }

  const completeMut = useMutation({
    mutationFn: async () => {
      setError('')
      let cid = customerId
      if (customerMode === 'new') {
        if (!newCustomer.full_name.trim()) throw new Error('Customer name is required.')
        const { data } = await createCustomer(newCustomer)
        cid = data.id
        qc.invalidateQueries({ queryKey: ['customers'] })
      } else if (!cid) throw new Error('Select a customer.')

      if (cart.length === 0) throw new Error('Add at least one item.')

      const accountId = customerAccountId && customerAccounts.some((a: CustomerAccount) => a.id === customerAccountId && a.customer_ids.includes(cid))
        ? customerAccountId
        : undefined

      let job: { id: string }
      if (linkToJobId) {
        job = { id: linkToJobId }
        const quote = await createAutoKeyQuote(linkToJobId, {
          line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
          tax_cents: tax,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(linkToJobId, quote.id)
        await updateAutoKeyJobStatus(linkToJobId, 'completed')
      } else {
        job = await createAutoKeyJob({
          customer_id: cid,
          customer_account_id: accountId || undefined,
          title: `POS sale ${new Date().toLocaleDateString()}`,
          key_quantity: 1,
          programming_status: 'not_required',
          priority: 'normal',
          status: 'awaiting_quote',
          deposit_cents: 0,
          cost_cents: total,
        }).then(r => r.data)
        const quote = await createAutoKeyQuote(job.id, {
          line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
          tax_cents: tax,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(job.id, quote.id)
        await updateAutoKeyJobStatus(job.id, 'collected')
      }

      return { job }
    },
    onSuccess: ({ job }) => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      qc.invalidateQueries({ queryKey: ['auto-key-job', job.id] })
      setCart([])
      setCustomerId('')
      setCustomerAccountId('')
      setLinkToJobId('')
      setNewCustomer({ full_name: '', email: '', phone: '' })
      setSuccessJobId(job.id)
      onComplete()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Sale failed.')),
  })

  if (successJobId) {
    return (
      <Card className="p-8 text-center">
        <p className="text-lg font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>Sale complete</p>
        <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
          Invoice created (unpaid). Send to customer via email or SMS, or record payment on the job.
        </p>
        <div className="flex gap-2 justify-center flex-wrap">
          <Button variant="secondary" onClick={() => setSuccessJobId(null)}>New sale</Button>
          <Button onClick={() => { setSuccessJobId(null); navigate(`/auto-key/${successJobId}`) }}>View job & record payment</Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Customer</h3>
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setCustomerMode('existing')}
              className={`flex-1 py-2 rounded text-sm font-medium border ${customerMode === 'existing' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
              style={customerMode === 'existing' ? { backgroundColor: 'rgba(245,158,11,0.2)', borderColor: 'var(--ms-accent)' } : {}}
            >Existing</button>
            <button
              onClick={() => setCustomerMode('new')}
              className={`flex-1 py-2 rounded text-sm font-medium border ${customerMode === 'new' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
              style={customerMode === 'new' ? { backgroundColor: 'rgba(245,158,11,0.2)', borderColor: 'var(--ms-accent)' } : {}}
            >Walk-in</button>
          </div>
          {customerMode === 'existing' ? (
            <>
              <CustomerSearchSelect customers={customers} value={customerId} onChange={id => { setCustomerId(id); setCustomerAccountId(''); setLinkToJobId('') }} />
              {customerId && (
                <>
                  <Select
                    label="B2B Account (optional)"
                    value={customerAccountId}
                    onChange={e => setCustomerAccountId(e.target.value)}
                  >
                    <option value="">Personal / no B2B</option>
                    {customerAccounts
                      .filter((a: CustomerAccount) => a.customer_ids.includes(customerId))
                      .map((a: CustomerAccount) => (
                        <option key={a.id} value={a.id}>
                          {a.name}{a.account_code ? ` (${a.account_code})` : ''}
                        </option>
                      ))}
                  </Select>
                  <Select
                    label="Link to Job (optional)"
                    value={linkToJobId}
                    onChange={e => setLinkToJobId(e.target.value)}
                  >
                    <option value="">Create new job</option>
                    {(activeJobsForCustomer ?? []).map((j: { id: string; job_number: string; vehicle_make?: string; vehicle_model?: string }) => (
                      <option key={j.id} value={j.id}>
                        {j.job_number} · {[j.vehicle_make, j.vehicle_model].filter(Boolean).join(' ') || 'No vehicle'}
                      </option>
                    ))}
                  </Select>
                </>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <Input label="Name *" value={newCustomer.full_name} onChange={e => setNewCustomer(f => ({ ...f, full_name: e.target.value }))} placeholder="Customer name" />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Phone" value={newCustomer.phone} onChange={e => setNewCustomer(f => ({ ...f, phone: e.target.value }))} placeholder="0412 345 678" />
                <Input label="Email" value={newCustomer.email} onChange={e => setNewCustomer(f => ({ ...f, email: e.target.value }))} placeholder="email@example.com" />
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Add items</h3>
          <div className="flex flex-wrap gap-2 mb-4">
            {POS_QUICK_ITEMS.map(({ label, desc, price }) => (
              <button
                key={label}
                type="button"
                onClick={() => addToCart(desc, price)}
                className="px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors"
                style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              >
                {label} — ${(price / 100).toFixed(2)}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              className="flex-1"
              placeholder="Description"
              value={customDesc}
              onChange={e => setCustomDesc(e.target.value)}
            />
            <Input
              type="number"
              step="0.01"
              min="0"
              placeholder="Price"
              className="w-24"
              value={customPrice}
              onChange={e => setCustomPrice(e.target.value)}
            />
            <Button
              variant="secondary"
              onClick={() => {
                const cents = Math.round(parseFloat(customPrice || '0') * 100)
                if (customDesc.trim() && cents > 0) {
                  addToCart(customDesc.trim(), cents)
                  setCustomDesc('')
                  setCustomPrice('')
                }
              }}
            >
              Add
            </Button>
          </div>
        </Card>
      </div>

      <Card className="p-5 h-fit">
        <h3 className="text-sm font-semibold uppercase tracking-wide mb-4 flex items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
          <ShoppingCart size={16} /> Cart
        </h3>
        {cart.length === 0 ? (
          <p className="text-sm py-6 text-center" style={{ color: 'var(--ms-text-muted)' }}>Cart empty. Add items above.</p>
        ) : (
          <div className="space-y-3 mb-4">
            {cart.map(line => (
              <div key={line.id} className="flex items-center justify-between gap-2 py-2 border-b" style={{ borderColor: 'var(--ms-border)' }}>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--ms-text)' }}>{line.description}</p>
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>${(line.unit_price_cents / 100).toFixed(2)} × {line.quantity}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button type="button" onClick={() => updateQty(line.id, line.quantity - 1)} className="w-7 h-7 rounded flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}><Minus size={14} /></button>
                  <span className="text-sm w-6 text-center" style={{ color: 'var(--ms-text)' }}>{line.quantity}</span>
                  <button type="button" onClick={() => updateQty(line.id, line.quantity + 1)} className="w-7 h-7 rounded flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}>+</button>
                  <button type="button" onClick={() => removeFromCart(line.id)} className="w-7 h-7 rounded flex items-center justify-center" style={{ color: '#C96A5A' }}><X size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="border-t pt-4" style={{ borderColor: 'var(--ms-border)' }}>
          <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>Subtotal</span><span style={{ color: 'var(--ms-text)' }}>${(subtotal / 100).toFixed(2)}</span></div>
          {tax > 0 && <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>Tax</span><span style={{ color: 'var(--ms-text)' }}>${(tax / 100).toFixed(2)}</span></div>}
          <div className="flex justify-between text-lg font-bold mt-2" style={{ color: 'var(--ms-accent)' }}><span>Total</span><span>${(total / 100).toFixed(2)}</span></div>
        </div>
        {error && <p className="text-sm mt-3" style={{ color: '#C96A5A' }}>{error}</p>}
        <Button
          className="w-full mt-4"
          onClick={() => completeMut.mutate()}
          disabled={completeMut.isPending || cart.length === 0}
        >
          <CreditCard size={16} />
          {completeMut.isPending ? 'Processing…' : 'Complete sale'}
        </Button>
      </Card>
    </div>
  )
}

function CreateQuoteModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [description, setDescription] = useState('Mobile service')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('120.00')
  const [tax, setTax] = useState('0.00')

  const quoteMut = useMutation({
    mutationFn: () =>
      createAutoKeyQuote(jobId, {
        line_items: [
          {
            description: description.trim() || 'Mobile service',
            quantity: Math.max(1, Number(quantity || '1')),
            unit_price_cents: Math.max(0, Math.round(parseFloat(unitPrice || '0') * 100)),
          },
        ],
        tax_cents: Math.max(0, Math.round(parseFloat(tax || '0') * 100)),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-quotes', jobId] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create quote.')),
  })

  return (
    <Modal title="Create Mobile Services Quote" onClose={onClose}>
      <div className="space-y-3">
        <Input label="Line item" value={description} onChange={e => setDescription(e.target.value)} />
        <div className="grid grid-cols-3 gap-3">
          <Input label="Qty" type="number" min="1" value={quantity} onChange={e => setQuantity(e.target.value)} />
          <Input label="Unit ($)" type="number" step="0.01" min="0" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} />
          <Input label="Tax ($)" type="number" step="0.01" min="0" value={tax} onChange={e => setTax(e.target.value)} />
        </div>
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex gap-2 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" onClick={() => quoteMut.mutate()} disabled={quoteMut.isPending}>
            {quoteMut.isPending ? 'Creating…' : 'Create Quote'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function WeekJobChip({
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

function WeekUnscheduledDropZone({
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

function WeekDayHeaderDrop({
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

function WeekHourDropCell({
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

function AutoKeyJobCard({
  job,
  users,
  isSolo,
  /** When true, skip per-job quotes/invoices/account queries so long lists do not fan out dozens of parallel API calls (can freeze the UI). */
  listMode = false,
}: {
  job: { id: string; job_number: string; title: string; customer_id: string; customer_name?: string | null; customer_phone?: string | null; customer_account_id?: string; assigned_user_id?: string; vehicle_make?: string; vehicle_model?: string; vehicle_year?: number; registration_plate?: string; key_type?: string; key_quantity: number; programming_status: string; status: JobStatus; priority?: string; created_at: string; salesperson?: string; scheduled_at?: string; job_address?: string; job_type?: string; tech_notes?: string }
  users: { id: string; full_name: string }[]
  isSolo?: boolean
  listMode?: boolean
}) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showQuoteModal, setShowQuoteModal] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [statusFeedback, setStatusFeedback] = useState('')
  const [confirmStatus, setConfirmStatus] = useState<JobStatus | null>(null)

  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
    enabled: !listMode,
  })
  const matchingAccounts = listMode ? [] : customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.customer_id))

  const { data: quotes = [] } = useQuery({
    queryKey: ['auto-key-quotes', job.id],
    queryFn: () => listAutoKeyQuotes(job.id).then(r => r.data),
    enabled: !listMode,
  })
  const { data: invoices = [] } = useQuery({
    queryKey: ['auto-key-invoices', job.id],
    queryFn: () => listAutoKeyInvoices(job.id).then(r => r.data),
    enabled: !listMode,
  })

  const latestQuote = quotes[0]
  const latestInvoice = invoices[0]
  const nextStatus = nextMobileStatus(job.status)
  const quickStatusLabel = nextStatus ? `Mark ${STATUS_LABELS[nextStatus] ?? nextStatus.replace(/_/g, ' ')}` : null

  const statusMut = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(job.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const updateAccountMut = useMutation({
    mutationFn: (customer_account_id: string | null) => updateAutoKeyJob(job.id, { customer_account_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const assignTechMut = useMutation({
    mutationFn: (assigned_user_id: string | null) => updateAutoKeyJob(job.id, { assigned_user_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const sendQuoteMut = useMutation({
    mutationFn: (quoteId: string) => sendAutoKeyQuote(quoteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-quotes', job.id] }),
  })

  const invoiceMut = useMutation({
    mutationFn: (quoteId: string) => createAutoKeyInvoiceFromQuote(job.id, quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', job.id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
  })

  const deleteMut = useMutation({
    mutationFn: () => deleteAutoKeyJob(job.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setShowDeleteConfirm(false)
      setDeleteError('')
    },
    onError: (err) => setDeleteError(getApiErrorMessage(err, 'Failed to delete job.')),
  })

  const handleStatusChange = async (status: JobStatus) => {
    if (['work_completed', 'failed_job'].includes(status)) {
      setConfirmStatus(status)
      return
    }
    setStatusFeedback('')
    const invoicesBefore = invoices.length
    await statusMut.mutateAsync(status)
    if (status !== 'work_completed') return

    const [{ data: latestQuotes }, { data: latestInvoices }] = await Promise.all([
      listAutoKeyQuotes(job.id),
      listAutoKeyInvoices(job.id),
    ])
    const newestQuote = latestQuotes[0]
    if (latestInvoices.length > invoicesBefore) {
      setStatusFeedback('Work completed — invoice created and payment link sent to customer.')
      return
    }
    if (!newestQuote) {
      setStatusFeedback('Work completed. No invoice auto-created because no quote exists yet.')
      return
    }
    if (newestQuote.status === 'declined') {
      setStatusFeedback('Work completed. No invoice auto-created because the latest quote is declined.')
      return
    }
    setStatusFeedback('Work completed. No new invoice was created (an invoice may already exist).')
  }

  return (
    <>
    <Card className="p-4">
      {showQuoteModal && <CreateQuoteModal jobId={job.id} onClose={() => setShowQuoteModal(false)} />}
      <div className="flex items-start justify-between gap-3">
        <div
          className="min-w-0 flex-1 cursor-pointer"
          onClick={() => navigate(`/auto-key/${job.id}`)}
          onKeyDown={e => e.key === 'Enter' && navigate(`/auto-key/${job.id}`)}
          role="button"
          tabIndex={0}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-mono font-semibold" style={{ color: 'var(--ms-accent)' }}>#{job.job_number}</p>
            {!isSolo && (
              <span className="text-[11px] font-medium rounded-full px-2 py-0.5" style={{ backgroundColor: job.assigned_user_id ? 'rgba(93,74,155,0.2)' : 'rgba(138,117,99,0.25)', color: job.assigned_user_id ? '#5D4A9B' : 'var(--ms-text-muted)' }}>
                {job.assigned_user_id ? (users.find(u => u.id === job.assigned_user_id)?.full_name ?? 'Assigned') : 'Unassigned'}
              </span>
            )}
            {job.priority === 'urgent' && (
              <span className="text-[11px] font-bold uppercase rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(201,100,90,0.15)', color: '#C96A5A' }}>
                Urgent
              </span>
            )}
            {job.priority === 'high' && (
              <span className="text-[11px] font-bold uppercase rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(200,130,50,0.15)', color: '#B87030' }}>
                High
              </span>
            )}
            {job.customer_account_id && (
              <span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: '#EAF4EA', color: '#2F6A3D' }}>
                B2B
              </span>
            )}
          </div>
          <span className="text-sm font-semibold hover:underline block" style={{ color: 'var(--ms-text)' }}>
            {job.title}
          </span>
          {job.customer_name && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{job.customer_name}</p>
          )}
          {job.customer_phone && (
            <a
              href={`tel:${job.customer_phone.replace(/\s/g, '')}`}
              className="inline-flex items-center gap-1 text-xs font-medium mt-0.5 touch-manipulation"
              style={{ color: 'var(--ms-accent)' }}
              onClick={e => e.stopPropagation()}
            >
              <Phone size={11} /> {job.customer_phone}
            </a>
          )}
          {(() => {
            const scheduledLabel = job.scheduled_at
              ? new Date(job.scheduled_at).toLocaleString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
              : null
            return scheduledLabel ? (
              <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-medium" style={{ backgroundColor: 'rgba(245,158,11,0.12)', color: 'var(--ms-accent)' }}>
                <Clock size={11} />
                {scheduledLabel}
              </span>
            ) : null
          })()}
          {(job.vehicle_make || job.vehicle_model || job.registration_plate) && (
            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
              <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                {[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}
                {job.vehicle_year ? ` · ${job.vehicle_year}` : ''}
                {job.registration_plate ? ` · ${job.registration_plate}` : ''}
              </p>
              {(() => {
                const complexity = parseAklComplexity(job.tech_notes)
                return complexity ? <AklComplexityPill complexity={complexity} /> : null
              })()}
            </div>
          )}
          {job.job_address && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>
              {job.job_address}
            </p>
          )}
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            Key: {job.key_type || 'Unspecified'} · Qty {job.key_quantity}
          </p>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            {formatDate(job.created_at)}{job.salesperson ? ` · ${job.salesperson}` : ''}
          </p>
          {job.job_type && (
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.job_type}</p>
          )}
          {job.job_address && (
            <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="inline-flex items-center gap-1 text-xs font-medium mt-1 hover:underline" style={{ color: 'var(--ms-accent)' }}>
              <MapPin size={12} /> Get directions
            </a>
          )}

          {latestQuote && (
            <p className="text-xs mt-2" style={{ color: 'var(--ms-text-mid)' }}>
              Latest quote: {formatCents(latestQuote.total_cents)} ({latestQuote.status})
            </p>
          )}
          {latestInvoice && (
            <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
              Latest invoice: {latestInvoice.invoice_number} · {formatCents(latestInvoice.total_cents)} ({latestInvoice.status})
            </p>
          )}
        </div>

        <div className="w-56 shrink-0" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between gap-2 mb-2">
            <Badge status={job.status} />
            <button
              type="button"
              aria-label={`Delete job ${job.job_number}`}
              onClick={() => { setDeleteError(''); setShowDeleteConfirm(true) }}
              className="h-7 w-7 rounded-full flex items-center justify-center transition-colors shrink-0"
              style={{ color: '#A4664A', border: '1px solid #E7C6B7', backgroundColor: '#FFF7F3' }}
            >
              <X size={14} />
            </button>
          </div>
          <Select
            value={job.status}
            onChange={e => { void handleStatusChange(e.target.value as JobStatus) }}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>)}
          </Select>
          {!isSolo && (
          <div className="mt-2">
            <Select
              label="Assign tech"
              value={job.assigned_user_id ?? ''}
              onChange={e => assignTechMut.mutate(e.target.value || null)}
              disabled={assignTechMut.isPending}
            >
              <option value="">Unassigned</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
            </Select>
          </div>
          )}
          {(matchingAccounts.length > 0 || job.customer_account_id) && (
            <div className="mt-2">
              <Select
                value={job.customer_account_id ?? ''}
                onChange={e => updateAccountMut.mutate(e.target.value || null)}
                disabled={updateAccountMut.isPending}
              >
                <option value="">No account</option>
                {matchingAccounts.map((account: CustomerAccount) => (
                  <option key={account.id} value={account.id}>
                    {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="mt-2 space-y-2">
            {nextStatus && (
              <button
                type="button"
                className="w-full inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none md:min-h-10 md:py-2"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', boxShadow: '0 2px 6px rgba(245,158,11,0.35)' }}
                onClick={() => { void handleStatusChange(nextStatus) }}
                disabled={statusMut.isPending}
              >
                {statusMut.isPending ? 'Updating…' : quickStatusLabel}
              </button>
            )}
            <Button variant="secondary" className="w-full" onClick={() => setShowQuoteModal(true)}>
              New Quote
            </Button>
            {latestQuote && latestQuote.status === 'draft' && (
              <Button className="w-full" onClick={() => sendQuoteMut.mutate(latestQuote.id)} disabled={sendQuoteMut.isPending}>
                {sendQuoteMut.isPending ? 'Sending…' : 'Mark Quote Sent'}
              </Button>
            )}
            {latestQuote && !latestInvoice && (
              <Button className="w-full" onClick={() => invoiceMut.mutate(latestQuote.id)} disabled={invoiceMut.isPending}>
                {invoiceMut.isPending ? 'Creating…' : 'Create Invoice from Quote'}
              </Button>
            )}
            {statusFeedback && (
              <p className="text-xs rounded-md px-2 py-1.5" style={{ backgroundColor: '#F8EBDD', color: '#6A3D21' }}>
                {statusFeedback}
              </p>
            )}
          </div>
        </div>
      </div>
    </Card>
      {confirmStatus && (
        <Modal
          title={`Mark as ${STATUS_LABELS[confirmStatus] ?? confirmStatus.replace(/_/g, ' ')}?`}
          onClose={() => setConfirmStatus(null)}
        >
          <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
            {confirmStatus === 'failed_job'
              ? 'This will mark the job as failed. No invoice will be auto-created.'
              : 'This will mark the job as work completed. An invoice will be auto-created and payment link sent to the customer.'}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setConfirmStatus(null)}>Cancel</Button>
            <Button
              className="flex-1"
              onClick={async () => {
                const s = confirmStatus
                setConfirmStatus(null)
                setStatusFeedback('')
                const invoicesBefore = invoices.length
                await statusMut.mutateAsync(s)
                if (s !== 'work_completed') return
                const [{ data: latestQuotes }, { data: latestInvoices }] = await Promise.all([
                  listAutoKeyQuotes(job.id),
                  listAutoKeyInvoices(job.id),
                ])
                const newestQuote = latestQuotes[0]
                if (latestInvoices.length > invoicesBefore) { setStatusFeedback('Work completed — invoice created and payment link sent to customer.'); return }
                if (!newestQuote) { setStatusFeedback('Work completed. No invoice auto-created because no quote exists yet.'); return }
                if (newestQuote.status === 'declined') { setStatusFeedback('Work completed. No invoice auto-created because the latest quote is declined.'); return }
                setStatusFeedback('Work completed. No new invoice was created (an invoice may already exist).')
              }}
              disabled={statusMut.isPending}
            >
              {statusMut.isPending ? 'Updating…' : 'Confirm'}
            </Button>
          </div>
        </Modal>
      )}
    {showDeleteConfirm && (
      <Modal
        title="Delete Mobile Services Job"
        onClose={() => { if (!deleteMut.isPending) { setShowDeleteConfirm(false); setDeleteError('') } }}
      >
        <div className="space-y-4">
          <p className="text-sm" style={{ color: 'var(--ms-text)' }}>Are you sure you want to delete this job?</p>
          <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>#{job.job_number} · {job.title}</p>
          </div>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>This action cannot be undone.</p>
          {deleteError && <p className="text-sm" style={{ color: '#C96A5A' }}>{deleteError}</p>}
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" className="flex-1" onClick={() => { if (!deleteMut.isPending) { setShowDeleteConfirm(false); setDeleteError('') } }}>Cancel</Button>
            <Button variant="danger" className="flex-1" onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}>
              {deleteMut.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    )}
    </>
  )
}

export default function AutoKeyJobsPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedView = searchParams.get('view')
  const initialView: 'jobs' | 'pos' | 'dispatch' | 'week' | 'map' | 'planner' | 'reports' =
    requestedView === 'jobs' ||
    requestedView === 'pos' ||
    requestedView === 'dispatch' ||
    requestedView === 'week' ||
    requestedView === 'map' ||
    requestedView === 'planner' ||
    requestedView === 'reports'
      ? requestedView
      : 'jobs'
  const initialJobsLayout: 'board' | 'list' =
    searchParams.get('jobs_layout') === 'list'
      ? 'list'
      : requestedView === 'dashboard' || !requestedView || requestedView === 'jobs'
        ? (searchParams.get('jobs_layout') === 'board' ? 'board' : 'board')
        : 'board'
  const initialStatus = searchParams.get('status')
  const initialOlderThanDays = Number.parseInt(searchParams.get('older_than_days') ?? '', 10)
  const initialDispatchDate = isYmd(searchParams.get('dispatch_date')) ? (searchParams.get('dispatch_date') as string) : ymdLocal(new Date())
  const initialDispatchTechFilter = searchParams.get('dispatch_tech') ?? ''
  const requestedMapRange = searchParams.get('map_range')
  const initialMapRangeMode =
    requestedMapRange === 'day' || requestedMapRange === 'week' || requestedMapRange === 'month'
      ? requestedMapRange
      : 'day'
  const initialWeekStart = isYmd(searchParams.get('week_start'))
    ? civilMondayOfWeekContaining(searchParams.get('week_start') as string)
    : civilMondayOfWeekContaining(ymdLocal(new Date()))
  const initialDirectory =
    initialStatus && AUTO_KEY_CLOSED_STATUSES.includes(initialStatus as typeof AUTO_KEY_CLOSED_STATUSES[number])
      ? 'completed'
      : 'active'
  const { role, shopCalendarTodayYmd, scheduleCalendarTimezone, sessionReady } = useAuth()
  const syncedShopCalendarDate = useRef(false)
  const weekAnchorSynced = useRef(false)
  const {
    showCreate,
    setShowCreate,
    showAddTech,
    setShowAddTech,
    showCommissionRules,
    setShowCommissionRules,
    showMoreActions,
    setShowMoreActions,
    plannerDetailJobId,
    setPlannerDetailJobId,
  } = useMobileServicesModals()
  const moreActionsRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!showMoreActions) return
    function handleOutside(e: MouseEvent) {
      if (moreActionsRef.current && !moreActionsRef.current.contains(e.target as Node)) {
        setShowMoreActions(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [showMoreActions])
  const [mapRangeMode, setMapRangeMode] = useState<'day' | 'week' | 'month'>(initialMapRangeMode)
  const [view, setView] = useState<'jobs' | 'pos' | 'dispatch' | 'week' | 'map' | 'planner' | 'reports'>(initialView)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed' | 'all'>(initialDirectory)
  const [statusFilter, setStatusFilter] = useState<string>(initialStatus ?? 'all')
  const [olderThanDays, setOlderThanDays] = useState<number>(Number.isFinite(initialOlderThanDays) ? initialOlderThanDays : 0)
  const [jobsLayout, setJobsLayout] = useState<'board' | 'list'>(initialJobsLayout)
  const [dispatchDate, setDispatchDate] = useState(initialDispatchDate)
  const [dispatchTechFilter, setDispatchTechFilter] = useState<string>(initialDispatchTechFilter)
  const [weekStart, setWeekStart] = useState(initialWeekStart)
  /** Week grid: tap Move then tap a day/slot if you do not want to drag. */
  /** Mobile: which day index (0-6) starts the 3-day window */
  const [mobileDayStart, setMobileDayStart] = useState(0)
  const [isMobileWidth, setIsMobileWidth] = useState(() => typeof window !== 'undefined' && window.innerWidth < 640)
  const weekDndSensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  )
  const [reportDateFrom, setReportDateFrom] = useState('')
  const [reportDateTo, setReportDateTo] = useState('')
  const [reportPreset, setReportPreset] = useState<'today' | 'week' | 'month' | 'last_month' | 'all' | 'custom'>('month')

  useEffect(() => {
    const handler = () => setIsMobileWidth(window.innerWidth < 640)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  useEffect(() => {
    if (!shopCalendarTodayYmd || !weekStart) return
    const days = Array.from({ length: 7 }, (_, i) => civilAddDays(weekStart, i))
    const todayIdx = days.indexOf(shopCalendarTodayYmd)
    setMobileDayStart(todayIdx >= 0 ? Math.min(todayIdx, 4) : 0)
  }, [weekStart, shopCalendarTodayYmd])

  useEffect(() => {
    if (!sessionReady || !shopCalendarTodayYmd || syncedShopCalendarDate.current) return
    setDispatchDate(shopCalendarTodayYmd)
    syncedShopCalendarDate.current = true
  }, [sessionReady, shopCalendarTodayYmd])

  useEffect(() => {
    if (!sessionReady || !shopCalendarTodayYmd || weekAnchorSynced.current) return
    setWeekStart(civilMondayOfWeekContaining(shopCalendarTodayYmd))
    weekAnchorSynced.current = true
  }, [sessionReady, shopCalendarTodayYmd])

  const { data: jobsRaw, isLoading, isError, error: jobsQueryError } = useQuery({
    queryKey: ['auto-key-jobs'],
    queryFn: () => listAutoKeyJobs().then(r => r.data),
  })
  const jobs = Array.isArray(jobsRaw) ? jobsRaw : []
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: view === 'pos' || view === 'map' || view === 'dispatch' || view === 'planner' || view === 'week',
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
    enabled: view === 'pos',
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const dispatchViews = view === 'dispatch' || view === 'map' || view === 'planner'
  const dispatchParams = useMemo(() => {
    if (!dispatchViews) return undefined
    const tech = dispatchTechFilter ? { assigned_user_id: dispatchTechFilter } : {}
    if (view === 'map') {
      if (mapRangeMode === 'day') return { date_from: dispatchDate, date_to: dispatchDate, ...tech }
      if (mapRangeMode === 'week') {
        const w = weekRangeFromYmd(dispatchDate)
        return { date_from: w.date_from, date_to: w.date_to, ...tech }
      }
      const mo = monthRangeFromYmd(dispatchDate)
      return { date_from: mo.date_from, date_to: mo.date_to, ...tech }
    }
    return { date_from: dispatchDate, date_to: dispatchDate, ...tech }
  }, [dispatchViews, view, dispatchDate, dispatchTechFilter, mapRangeMode])

  const mapRangeLabel = useMemo(() => {
    if (view !== 'map') return ''
    if (mapRangeMode === 'day') return `Showing jobs scheduled on ${formatDate(dispatchDate)}.`
    if (mapRangeMode === 'week') {
      const w = weekRangeFromYmd(dispatchDate)
      return `Showing jobs scheduled ${formatDate(w.date_from)} – ${formatDate(w.date_to)}.`
    }
    const mo = monthRangeFromYmd(dispatchDate)
    return `Showing jobs scheduled ${formatDate(mo.date_from)} – ${formatDate(mo.date_to)}.`
  }, [view, mapRangeMode, dispatchDate])

  const { data: dispatchJobs = [], isLoading: dispatchLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'dispatch', dispatchDate, dispatchTechFilter, view === 'map' ? mapRangeMode : 'single-day'],
    queryFn: () => listAutoKeyJobs(dispatchParams!).then(r => r.data),
    enabled: dispatchViews && !!dispatchParams,
  })

  const weekEnd = civilAddDays(weekStart, 6)
  const weekParams = view === 'week' ? { date_from: weekStart, date_to: weekEnd, include_unscheduled: true } : undefined

  const {
    reportsQuery: { data: autoKeyReports, isLoading: reportsLoading, isError: reportsError, error: reportsErr },
    commissionQuery: { data: commissionReport, isLoading: commissionLoading, isError: commissionError, error: commissionErr },
  } = useAutoKeyReportData({
    view,
    role,
    preset: reportPreset,
    customDateFrom: reportDateFrom,
    customDateTo: reportDateTo,
  })
  const { tomorrowJobs, sendRemindersMut } = useAutoKeyDayBeforeReminders()

  const statusMut = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus }) => updateAutoKeyJobStatus(jobId, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const rescheduleMut = useMutation({
    mutationFn: ({ jobId, scheduled_at }: { jobId: string; scheduled_at: string | null }) =>
      updateAutoKeyJob(jobId, scheduled_at ? { scheduled_at } : { scheduled_at: null }),
    onSuccess: () => {
      setWeekScheduleErr(null)
      setWeekRelocateJobId(null)
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs', 'dashboard'] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs', 'dispatch'] })
    },
    onError: (err: unknown) => {
      setWeekScheduleErr(getApiErrorMessage(err, 'Could not update the job time. Check your connection and that you can edit jobs.'))
    },
  })
  const { data: weekJobs = [], isLoading: weekLoading, isError: weekError, error: weekErr, refetch: refetchWeek } = useQuery({
    queryKey: ['auto-key-jobs', 'week', weekStart, weekEnd],
    queryFn: () => listAutoKeyJobs(weekParams!).then(r => r.data),
    enabled: view === 'week' && !!weekParams,
  })
  const {
    weekRelocateJobId,
    setWeekRelocateJobId,
    activeWeekJobId,
    weekScheduleErr,
    setWeekScheduleErr,
    handleWeekDragStart,
    handleWeekDragCancel,
    handleWeekDragEnd,
  } = useWeekSchedulerDnD({
    onReschedule: (jobId, scheduledAt) => rescheduleMut.mutate({ jobId, scheduled_at: scheduledAt }),
    scheduledForDay: (jobId, dayYmd) => isoScheduledOnDayKeepingShopTime(jobId, dayYmd, weekJobs, scheduleCalendarTimezone),
    scheduledForSlot: (dayYmd, hour) => weekSlotScheduledAt(dayYmd, hour, scheduleCalendarTimezone),
  })

  const activeWeekJob = useMemo<WeekSchedulerJob | null>(() => {
    if (!activeWeekJobId) return null
    const match = weekJobs.find((job: { id: string }) => job.id === activeWeekJobId) as WeekSchedulerJob | undefined
    return match ?? null
  }, [activeWeekJobId, weekJobs])

  const autoKeyClosedStatuses = new Set(AUTO_KEY_CLOSED_STATUSES)
  const isClosed = (status: JobStatus) => autoKeyClosedStatuses.has(status as typeof AUTO_KEY_CLOSED_STATUSES[number])
  const unscheduledJobs = view === 'dispatch'
    ? jobs.filter((j: { scheduled_at?: string; status: JobStatus; assigned_user_id?: string }) => {
      if (j.scheduled_at) return false
      if (dispatchTechFilter && j.assigned_user_id !== dispatchTechFilter) return false
      return !isClosed(j.status)
    })
    : []
  const isSolo = users.length <= 1
  const filteredJobs = jobs.filter((j: { id: string; job_number: string; title: string; status: JobStatus; created_at: string; vehicle_make?: string; vehicle_model?: string; registration_plate?: string; customer_name?: string | null }) => {
    const q = search.trim().toLowerCase()
    const jn = String(j.job_number ?? '')
    const jt = String(j.title ?? '')
    const matchSearch =
      !q ||
      jn.toLowerCase().includes(q) ||
      jt.toLowerCase().includes(q) ||
      (j.vehicle_make && String(j.vehicle_make).toLowerCase().includes(q)) ||
      (j.vehicle_model && String(j.vehicle_model).toLowerCase().includes(q)) ||
      (j.registration_plate && String(j.registration_plate).toLowerCase().includes(q)) ||
      (j.customer_name && String(j.customer_name).toLowerCase().includes(q))
    const inDirectory = jobDirectoryView === 'all' ? true : jobDirectoryView === 'active' ? !isClosed(j.status) : isClosed(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    const created = j.created_at ? String(j.created_at) : ''
    const matchAge = olderThanDays > 0 ? (created ? daysInShop(created) >= olderThanDays : false) : true
    return matchSearch && inDirectory && matchStatus && matchAge
  })
  const statusOptions = jobDirectoryView === 'all'
    ? [...AUTO_KEY_ACTIVE_STATUSES, ...AUTO_KEY_CLOSED_STATUSES]
    : jobDirectoryView === 'active' ? [...AUTO_KEY_ACTIVE_STATUSES] : [...AUTO_KEY_CLOSED_STATUSES]

  useEffect(() => {
    if (statusFilter === 'all') return
    const allowed: readonly string[] = jobDirectoryView === 'active' ? AUTO_KEY_ACTIVE_STATUSES : AUTO_KEY_CLOSED_STATUSES
    if (!allowed.includes(statusFilter)) {
      setStatusFilter('all')
    }
  }, [jobDirectoryView, statusFilter])
  const activeCount = jobs.filter((j: { status: JobStatus }) => !isClosed(j.status)).length
  const completedCount = jobs.filter((j: { status: JobStatus }) => isClosed(j.status)).length


  const sortedJobsDirectory = useMemo(() => {
    if (view !== 'jobs') return []
    const todayYmd = ymdLocal(new Date())
    return [...filteredJobs].sort((a, b) => {
      const ja = a as AutoKeyJob
      const jb = b as AutoKeyJob
      const aToday = ja.scheduled_at && ymdLocal(new Date(ja.scheduled_at)) === todayYmd ? 0 : 1
      const bToday = jb.scheduled_at && ymdLocal(new Date(jb.scheduled_at)) === todayYmd ? 0 : 1
      if (aToday !== bToday) return aToday - bToday
      if (ja.scheduled_at && jb.scheduled_at) {
        return new Date(ja.scheduled_at).getTime() - new Date(jb.scheduled_at).getTime()
      }
      if (ja.scheduled_at) return -1
      if (jb.scheduled_at) return 1
      return new Date(jb.created_at).getTime() - new Date(ja.created_at).getTime()
    })
  }, [view, filteredJobs])

  useEffect(() => {
    const next = new URLSearchParams()
    if (view !== 'jobs') next.set('view', view)
    if (statusFilter !== 'all') next.set('status', statusFilter)
    if (olderThanDays > 0) next.set('older_than_days', String(olderThanDays))
    if (view === 'dispatch' || view === 'map' || view === 'planner') {
      next.set('dispatch_date', dispatchDate)
      if (dispatchTechFilter) next.set('dispatch_tech', dispatchTechFilter)
    }
    if (view === 'map') {
      next.set('map_range', mapRangeMode)
    }
    if (view === 'week') {
      next.set('week_start', weekStart)
    }
    if (view === 'jobs' && jobsLayout === 'board') {
      next.set('jobs_layout', 'board')
    }
    setSearchParams(next, { replace: true })
  }, [
    jobsLayout,
    dispatchDate,
    dispatchTechFilter,
    mapRangeMode,
    olderThanDays,
    setSearchParams,
    statusFilter,
    view,
    weekStart,
  ])

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <PageHeader
          title="Mobile Services"
          action={(
            <div className="flex items-center gap-2">
              {/* Mobile: ··· overflow menu + New Job */}
              <div className="relative sm:hidden" ref={moreActionsRef}>
                <Button variant="secondary" onClick={() => setShowMoreActions(m => !m)} type="button" aria-label="More actions">···</Button>
                {showMoreActions && (
                  <div
                    className="absolute left-0 top-full mt-1 z-20 rounded-xl flex flex-col gap-1 p-2 shadow-xl"
                    style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', minWidth: '180px' }}
                  >
                    {role === 'owner' && (
                      <Button variant="secondary" onClick={() => { setShowAddTech(true); setShowMoreActions(false) }} type="button">
                        <UserPlus size={16} />Add technician
                      </Button>
                    )}
                    {(role === 'owner' || role === 'manager') && (
                      <Button variant="secondary" onClick={() => { setShowCommissionRules(true); setShowMoreActions(false) }} type="button">
                        Commission rules
                      </Button>
                    )}
                    <Button variant="secondary" onClick={() => { navigate('/auto-key/team'); setShowMoreActions(false) }} type="button">
                      <Users size={16} />Team
                    </Button>
                  </div>
                )}
              </div>
              <Button onClick={() => setShowCreate(true)} type="button" className="sm:hidden"><Plus size={16} />New Job</Button>
              {/* Desktop: show all buttons */}
              {role === 'owner' && (
                <Button variant="secondary" onClick={() => setShowAddTech(true)} type="button" className="hidden sm:inline-flex">
                  <UserPlus size={16} />Add technician
                </Button>
              )}
              {(role === 'owner' || role === 'manager') && (
                <Button variant="secondary" onClick={() => setShowCommissionRules(true)} type="button" className="hidden sm:inline-flex">
                  Commission rules
                </Button>
              )}
              <Button variant="secondary" onClick={() => navigate('/auto-key/team')} type="button" className="hidden sm:inline-flex">
                <Users size={16} />Team
              </Button>
              <Button onClick={() => setShowCreate(true)} type="button" className="hidden sm:inline-flex"><Plus size={16} />New Job</Button>
            </div>
          )}
        />
      </div>
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Mobile and in-shop key cutting, programming, and replacement. Plan your day, track mobile vs shop work.{' '}
        <Link to="/auto-key/team" className="font-semibold whitespace-nowrap" style={{ color: 'var(--ms-accent)' }}>
          Team roster →
        </Link>
      </p>
      <MobileServicesSubNav className="mb-5" />
      <div className="mb-5 -mx-4 px-4 overflow-x-auto sm:mx-0 sm:px-0">
        <div
          className="inline-flex items-center gap-1 rounded-lg p-1"
          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
        >
          {([
            { key: 'list', label: 'List', icon: <List size={15} /> },
            { key: 'kanban', label: 'Kanban', icon: <LayoutGrid size={15} /> },
            { key: 'map', label: 'Map', icon: <MapIcon size={15} /> },
            { key: 'planner', label: 'Planner', icon: <CalendarDays size={15} /> },
            { key: 'pos', label: 'POS', icon: <CreditCard size={15} /> },
            { key: 'reports', label: 'Reports', icon: <BarChart3 size={15} /> },
          ] as const).map(tab => {
            const active =
              (tab.key === 'list' && view === 'jobs' && jobsLayout === 'list') ||
              (tab.key === 'kanban' && view === 'jobs' && jobsLayout === 'board') ||
              (tab.key === 'planner' && (view === 'planner' || view === 'dispatch' || view === 'week')) ||
              (tab.key === 'map' && view === 'map') ||
              (tab.key === 'pos' && view === 'pos') ||
              (tab.key === 'reports' && view === 'reports')
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => {
                  if (tab.key === 'list') { setView('jobs'); setJobsLayout('list') }
                  else if (tab.key === 'kanban') { setView('jobs'); setJobsLayout('board') }
                  else if (tab.key === 'planner') { setView('week') }
                  else setView(tab.key as typeof view)
                }}
                className="flex items-center gap-1.5 rounded-md whitespace-nowrap transition-colors"
                style={{
                  padding: '7px 14px',
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  color: active ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                  backgroundColor: active ? 'var(--ms-accent-pop)' : 'transparent',
                  border: active ? '1px solid var(--ms-accent-light)' : '1px solid transparent',
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {showCreate && <NewAutoKeyJobModal onClose={() => setShowCreate(false)} />}
      {showAddTech && (
        <AddTechnicianModal
          onClose={() => setShowAddTech(false)}
          onAdded={() => navigate('/auto-key/team', { state: { addedTech: true } })}
        />
      )}
      {showCommissionRules && (
        <MobileCommissionRulesModal onClose={() => setShowCommissionRules(false)} />
      )}
      {plannerDetailJobId && (
        <PlannerJobDetailModal
          jobId={plannerDetailJobId}
          onClose={() => setPlannerDetailJobId(null)}
          customers={customers}
          users={users}
        />
      )}

      {view === 'jobs' && jobsLayout === 'board' && (
        <>
          <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Mobile Services — Kanban</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                {filteredJobs.length} active job{filteredJobs.length !== 1 ? 's' : ''} across {AUTO_KEY_KANBAN_COLUMNS.length} stages
              </p>
            </div>
          </div>
          {isLoading ? (
            <Spinner />
          ) : isError ? (
            <p className="text-sm rounded-lg px-4 py-3" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-error)' }}>
              {getApiErrorMessage(jobsQueryError, 'Could not load jobs.')}
            </p>
          ) : (
            <KanbanBoard
              jobs={sortedJobsDirectory as AutoKeyJob[]}
              columns={AUTO_KEY_KANBAN_COLUMNS}
              onStatusChange={(jobId, nextStatus) =>
                statusMut.mutate({ jobId, status: nextStatus as JobStatus })
              }
              renderCard={(job, column) => {
                const tech = users.find((u: { id: string; full_name: string }) => u.id === job.assigned_user_id)?.full_name ?? null
                const descParts = [
                  [job.vehicle_year, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' '),
                  job.registration_plate,
                ].filter(Boolean)
                return (
                  <KanbanJobCard
                    jobNumber={job.job_number}
                    title={job.title}
                    description={descParts.join(' · ') || job.description || undefined}
                    customerName={job.customer_name ?? null}
                    priority={job.priority}
                    daysInShop={daysInShop(job.created_at)}
                    quoteCents={job.cost_cents > 0 ? job.cost_cents : undefined}
                    techName={tech}
                    techKey={job.assigned_user_id ?? null}
                    accentColor={column.color}
                    href={`/mobile-services/jobs/${job.id}`}
                    draggable={!statusMut.isPending}
                    onDragStart={e => {
                      e.dataTransfer.setData('text/job-id', job.id)
                      e.dataTransfer.effectAllowed = 'move'
                    }}
                    extras={job.scheduled_at ? (
                      <span
                        className="inline-flex items-center gap-1"
                        style={{
                          backgroundColor: 'var(--ms-accent-light)',
                          color: 'var(--ms-accent)',
                          fontSize: 10,
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: 99,
                        }}
                      >
                        <Calendar size={10} />
                        {formatDate(job.scheduled_at)}
                      </span>
                    ) : null}
                  />
                )
              }}
            />
          )}
        </>
      )}

      {view === 'jobs' && jobsLayout === 'list' && (
        <>
          {/* Filter chips + search */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {([
                { label: 'Active', dir: 'active' as const, status: 'all' },
                { label: 'All', dir: 'all' as const, status: 'all' },
                { label: 'Awaiting Quote', dir: 'active' as const, status: 'awaiting_quote' },
                { label: 'Booking Confirmed', dir: 'active' as const, status: 'booking_confirmed' },
                { label: 'Work Completed', dir: 'active' as const, status: 'work_completed' },
                { label: 'Invoice Paid', dir: 'completed' as const, status: 'invoice_paid' },
              ]).map(chip => {
                const isActive = jobDirectoryView === chip.dir && statusFilter === chip.status
                return (
                  <button
                    key={chip.label}
                    type="button"
                    onClick={() => { setJobDirectoryView(chip.dir); setStatusFilter(chip.status) }}
                    className="rounded-full text-xs font-semibold transition-colors"
                    style={{
                      padding: '5px 13px',
                      backgroundColor: isActive ? 'var(--ms-accent)' : 'var(--ms-surface)',
                      color: isActive ? '#fff' : 'var(--ms-text-mid)',
                      border: `1px solid ${isActive ? 'var(--ms-accent)' : 'var(--ms-border)'}`,
                    }}
                  >
                    {chip.label}
                  </button>
                )
              })}
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5" style={{ color: 'var(--ms-text-muted)' }} />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search jobs…"
                className="pl-8 pr-3 py-1.5 rounded-lg border text-sm w-48"
                style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)', color: 'var(--ms-text)' }}
              />
            </div>
          </div>
          {isLoading ? (
            <Spinner />
          ) : isError ? (
            <p className="text-sm rounded-lg px-4 py-3" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-error)' }}>
              {getApiErrorMessage(jobsQueryError, 'Could not load jobs.')}
            </p>
          ) : filteredJobs.length === 0 ? (
            <EmptyState message={jobs.length === 0 ? 'No Mobile Services jobs yet.' : 'No jobs match your filters.'} />
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
                      {['#', 'CUSTOMER', 'VEHICLE', 'JOB TYPE', 'STATUS', 'TECH', 'SCHEDULED', 'QUOTE'].map(h => (
                        <th
                          key={h}
                          className="px-4 py-2.5 text-left font-semibold tracking-wider text-[11px]"
                          style={{ color: 'var(--ms-text-muted)' }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedJobsDirectory.map((job, i) => {
                      const tech = users.find((u: { id: string; full_name: string }) => u.id === job.assigned_user_id)?.full_name
                      const vehicle = [job.vehicle_year, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')
                      const sched = job.scheduled_at
                        ? new Date(job.scheduled_at).toLocaleString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                        : null
                      const col = findColumnForStatus(AUTO_KEY_KANBAN_COLUMNS, job.status)
                      return (
                        <tr
                          key={job.id}
                          className="group cursor-pointer"
                          style={{ borderBottom: i < sortedJobsDirectory.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                          onClick={() => window.location.href = `/mobile-services/jobs/${job.id}`}
                          onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--ms-hover)')}
                          onMouseLeave={e => (e.currentTarget.style.backgroundColor = '')}
                        >
                          <td className="px-4 py-3 font-semibold whitespace-nowrap" style={{ color: 'var(--ms-accent)' }}>
                            #{job.job_number}
                          </td>
                          <td className="px-4 py-3">
                            <p className="font-medium whitespace-nowrap" style={{ color: 'var(--ms-text)' }}>{job.customer_name ?? '—'}</p>
                            {job.customer_phone && <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.customer_phone}</p>}
                          </td>
                          <td className="px-4 py-3">
                            <p className="whitespace-nowrap" style={{ color: 'var(--ms-text)' }}>{vehicle || '—'}</p>
                            {job.registration_plate && <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.registration_plate}</p>}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--ms-text-mid)' }}>
                            {job.job_type ?? '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span
                              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                              style={{
                                backgroundColor: col ? col.bg : 'var(--ms-bg)',
                                color: col ? col.color : 'var(--ms-text-muted)',
                              }}
                            >
                              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: col?.color ?? 'var(--ms-text-muted)', flexShrink: 0 }} />
                              {STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--ms-text-mid)' }}>
                            {tech ?? <span style={{ color: 'var(--ms-text-muted)' }}>Unassigned</span>}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: sched ? 'var(--ms-accent)' : 'var(--ms-text-muted)' }}>
                            {sched ?? '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-semibold" style={{ color: job.cost_cents > 0 ? 'var(--ms-text)' : 'var(--ms-text-muted)' }}>
                            {job.cost_cents > 0 ? formatCents(job.cost_cents) : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {view === 'pos' && (
        <POSView
          customers={customers}
          customerAccounts={customerAccounts}
          onComplete={() => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })}
        />
      )}

      {view === 'dispatch' && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Date</label>
              <input
                type="date"
                value={dispatchDate}
                onChange={e => setDispatchDate(e.target.value)}
                className="rounded-lg border px-3 py-2 text-sm"
                style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              />
            </div>
            {!isSolo && (
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Tech</label>
              <Select
                value={dispatchTechFilter}
                onChange={e => setDispatchTechFilter(e.target.value)}
                className="min-w-[160px]"
                style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              >
                <option value="">All technicians</option>
                {users.map((u: { id: string; full_name: string }) => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </Select>
            </div>
            )}
            <Button
              variant="secondary"
              onClick={() => sendRemindersMut.mutate()}
              disabled={sendRemindersMut.isPending}
              className="ml-auto"
            >
              {sendRemindersMut.isPending
                ? 'Sending…'
                : tomorrowJobs.length > 0
                ? `Send reminders (${tomorrowJobs.length} job${tomorrowJobs.length !== 1 ? 's' : ''} tomorrow)`
                : 'Send day-before reminders'}
            </Button>
          </div>

          {dispatchLoading ? <Spinner /> : (
            <>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                  {isSolo ? "Today's schedule" : 'Scheduled for'} {formatDate(dispatchDate)}
                </h3>
                {dispatchJobs.length === 0 ? (
                  <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>No jobs scheduled for this date.</p>
                ) : isSolo || dispatchTechFilter ? (
                  <div className="space-y-2">
                    {dispatchJobs.map((job: object) => (
                      <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} listMode />
                    ))}
                  </div>
                ) : (
                  (() => {
                    const byTech = new Map<string, object[]>()
                    for (const j of dispatchJobs) {
                      const uid = (j as { assigned_user_id?: string }).assigned_user_id ?? null
                      const key = uid ?? '__unassigned__'
                      if (!byTech.has(key)) byTech.set(key, [])
                      byTech.get(key)!.push(j)
                    }
                    const unassigned = byTech.get('__unassigned__') ?? []
                    const assigned = [...byTech.entries()].filter(([k]) => k !== '__unassigned__').sort((a, b) => {
                      const na = users.find((u: { id: string }) => u.id === a[0])?.full_name ?? ''
                      const nb = users.find((u: { id: string }) => u.id === b[0])?.full_name ?? ''
                      return na.localeCompare(nb)
                    })
                    return (
                      <div className="space-y-4">
                        {assigned.map(([uid, techJobs]) => (
                          <div key={uid}>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-accent)' }}>
                              {users.find((u: { id: string }) => u.id === uid)?.full_name ?? 'Tech'}
                            </p>
                            <div className="space-y-2">
                              {techJobs.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} listMode />
                              ))}
                            </div>
                          </div>
                        ))}
                        {unassigned.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>Unassigned</p>
                            <div className="space-y-2">
                              {unassigned.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} listMode />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })()
                )}
              </div>

              {unscheduledJobs.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                    Unscheduled ({unscheduledJobs.length})
                  </h3>
                  <div className="space-y-2">
                    {unscheduledJobs.map((job: object) => (
                      <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} listMode />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {view === 'week' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={() => {
                setWeekStart(civilAddDays(weekStart, -7))
              }}><ChevronLeft size={16} /></Button>
              <span className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                {formatDate(weekStart)} – {formatDate(weekEnd)}
              </span>
              <Button variant="secondary" onClick={() => {
                setWeekStart(civilAddDays(weekStart, 7))
              }}><ChevronRight size={16} /></Button>
            </div>
          </div>
          {weekError && !weekLoading && (
            <Card className="p-4">
              <p className="text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(weekErr, 'Could not load jobs for this week.')}</p>
              <Button variant="secondary" className="mt-3" type="button" onClick={() => refetchWeek()}>Retry</Button>
            </Card>
          )}
          {weekLoading ? <Spinner /> : weekError ? null : (
            <div className="space-y-4">
              {weekScheduleErr && (
                <Card className="p-3" style={{ borderColor: '#E7C6B7', backgroundColor: '#FFF7F3' }}>
                  <p className="text-sm" style={{ color: '#8B3A3A' }}>{weekScheduleErr}</p>
                  <Button variant="secondary" className="mt-2" type="button" onClick={() => setWeekScheduleErr(null)}>Dismiss</Button>
                </Card>
              )}
              <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                {weekJobs.length === 0
                  ? 'No jobs in this week (nothing scheduled and no unscheduled jobs). Create a job or schedule one to see it here.'
                  : `${weekJobs.length} job${weekJobs.length !== 1 ? 's' : ''} in this view. Drag the whole booking card to a day header (same time) or an hour cell. Use Open to jump into a job, and Move on phones/tablets for tap-to-place scheduling.`}
              </p>
              {weekRelocateJobId && (() => {
                const j = weekJobs.find((x: { id: string }) => x.id === weekRelocateJobId)
                const label = j ? `#${(j as { job_number: string }).job_number}` : 'Job'
                return (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm" style={{ backgroundColor: 'rgba(245, 158, 11, 0.12)', borderColor: 'var(--ms-accent)', color: 'var(--ms-text)' }}>
                    <span className="font-medium">Moving {label}</span>
                    <span style={{ color: 'var(--ms-text-muted)' }}>— tap a day or time below, or</span>
                    <Button
                      variant="secondary"
                      type="button"
                      className="!py-1 !px-2 text-xs"
                      onClick={() => {
                        rescheduleMut.mutate({ jobId: weekRelocateJobId, scheduled_at: null })
                      }}
                    >
                      Clear time
                    </Button>
                    <Button variant="secondary" type="button" className="!py-1 !px-2 text-xs" onClick={() => setWeekRelocateJobId(null)}>Cancel</Button>
                  </div>
                )
              })()}
              {(() => {
                const unscheduled = weekJobs.filter((j: { scheduled_at?: string }) => !j.scheduled_at) as WeekSchedulerJob[]
                return (
                  <DndContext
                    sensors={weekDndSensors}
                    collisionDetection={closestCenter}
                    onDragStart={handleWeekDragStart}
                    onDragCancel={handleWeekDragCancel}
                    onDragEnd={handleWeekDragEnd}
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
                          <span className="hidden sm:inline">Unscheduled — drag the whole card to a slot, or Move → tap destination; drop a card here to clear time</span>
                          <span className="sm:hidden">Unscheduled</span>
                        </h3>
                        <span
                          className="sm:hidden inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold cursor-default select-none"
                          style={{ backgroundColor: 'var(--ms-border)', color: 'var(--ms-text-muted)' }}
                          title="Tap Move on a card, then tap a time slot to schedule it. Drag cards on desktop."
                          aria-label="Tap Move on a card then tap a time slot to schedule it"
                        >
                          ?
                        </span>
                      </div>
                      <WeekUnscheduledDropZone
                        canTapPlace={!!weekRelocateJobId}
                        onClick={(ev) => {
                          if (!weekRelocateJobId) return
                          if ((ev.target as HTMLElement).closest('[data-week-job-chip]')) return
                          rescheduleMut.mutate({ jobId: weekRelocateJobId, scheduled_at: null })
                        }}
                      >
                        {unscheduled.map((job) => (
                          <WeekJobChip
                            key={job.id}
                            job={job}
                            customerName={job.customer_name ?? (job.customer_id ? customers.find((c: { id: string }) => c.id === job.customer_id)?.full_name : undefined)}
                            assignedTechName={job.assigned_user_id ? users.find((u: { id: string }) => u.id === job.assigned_user_id)?.full_name : undefined}
                            selected={weekRelocateJobId === job.id}
                            isDragging={activeWeekJobId === job.id}
                            onMoveToggle={() => setWeekRelocateJobId((cur) => (cur === job.id ? null : job.id))}
                          />
                        ))}
                      </WeekUnscheduledDropZone>
                    </div>

                    {(() => {
                      const visibleDayIndices = isMobileWidth
                        ? [mobileDayStart, mobileDayStart + 1, mobileDayStart + 2].filter(i => i < 7)
                        : Array.from({ length: 7 }, (_, i) => i)
                      const colTemplate = isMobileWidth
                        ? `40px repeat(${visibleDayIndices.length}, 1fr)`
                        : '80px repeat(7, minmax(120px, 1fr))'
                      return (
                        <>
                          {isMobileWidth && (
                            <div className="flex items-center justify-between mb-2 px-1">
                              <button
                                type="button"
                                disabled={mobileDayStart === 0}
                                onClick={() => setMobileDayStart(d => Math.max(0, d - 1))}
                                className="p-2 rounded-lg disabled:opacity-30"
                                style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}
                              >
                                <ChevronLeft size={16} style={{ color: 'var(--ms-text-muted)' }} />
                              </button>
                              <span className="text-xs font-semibold" style={{ color: 'var(--ms-text-muted)' }}>
                                {visibleDayIndices.map(i => {
                                  const ds = civilAddDays(weekStart, i)
                                  const [, , cd] = ds.split('-').map(Number)
                                  const [cy, cm] = ds.split('-').map(Number)
                                  const name = new Date(Date.UTC(cy, cm - 1, cd)).toLocaleDateString('en-AU', { weekday: 'short', timeZone: 'UTC' })
                                  return `${name} ${cd}`
                                }).join(' · ')}
                              </span>
                              <button
                                type="button"
                                disabled={mobileDayStart >= 4}
                                onClick={() => setMobileDayStart(d => Math.min(4, d + 1))}
                                className="p-2 rounded-lg disabled:opacity-30"
                                style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}
                              >
                                <ChevronRight size={16} style={{ color: 'var(--ms-text-muted)' }} />
                              </button>
                            </div>
                          )}
                          <div className="max-h-[min(85vh,900px)] overflow-y-auto">
                            <div className="grid gap-2" style={{ gridTemplateColumns: colTemplate }}>
                              <div />
                              {visibleDayIndices.map((i) => {
                                const dayStr = civilAddDays(weekStart, i)
                                const [cy, cm, cd] = dayStr.split('-').map(Number)
                                const civilUtc = Date.UTC(cy, cm - 1, cd)
                                const dayName = new Date(civilUtc).toLocaleDateString('en-AU', { weekday: 'short', timeZone: 'UTC' })
                                const dayNum = cd
                                const isToday = Boolean(shopCalendarTodayYmd && dayStr === shopCalendarTodayYmd)
                                return (
                                  <WeekDayHeaderDrop
                                    key={dayStr}
                                    dayStr={dayStr}
                                    dayName={dayName}
                                    dayNum={dayNum}
                                    isToday={isToday}
                                    canTapPlace={!!weekRelocateJobId}
                                    onClick={() => {
                                      if (!weekRelocateJobId) return
                                      const next = isoScheduledOnDayKeepingShopTime(weekRelocateJobId, dayStr, weekJobs, scheduleCalendarTimezone)
                                      rescheduleMut.mutate({ jobId: weekRelocateJobId, scheduled_at: next })
                                    }}
                                  />
                                )
                              })}
                              {WEEK_SCHEDULE_HOURS.map(hour => (
                                <Fragment key={hour}>
                                  <div className="py-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                                    {String(hour).padStart(2, '0')}:00
                                  </div>
                                  {visibleDayIndices.map((i) => {
                                    const dayStr = civilAddDays(weekStart, i)
                                    const slotStartMs = new Date(zonedWallTimeToUtcIso(dayStr, hour, 0, scheduleCalendarTimezone)).getTime()
                                    const slotEndMs = new Date(zonedWallTimeToUtcIso(dayStr, hour + 1, 0, scheduleCalendarTimezone)).getTime()
                                    const inSlot = weekJobs.filter((j: { scheduled_at?: string }) => {
                                      if (!j.scheduled_at) return false
                                      const t = new Date(j.scheduled_at).getTime()
                                      return t >= slotStartMs && t < slotEndMs
                                    }) as WeekSchedulerJob[]
                                    const newScheduledAt = weekSlotScheduledAt(dayStr, hour, scheduleCalendarTimezone)
                                    return (
                                      <WeekHourDropCell
                                        key={`${dayStr}-${hour}`}
                                        dropId={weekSlotDropId(dayStr, hour)}
                                        canTapPlace={!!weekRelocateJobId}
                                        onClick={(ev) => {
                                          if (!weekRelocateJobId) return
                                          const t = ev.target as HTMLElement
                                          if (t.closest('a')) return
                                          if (t.closest('button')) return
                                          if (t.closest('[data-week-job-chip]')) return
                                          rescheduleMut.mutate({ jobId: weekRelocateJobId, scheduled_at: newScheduledAt })
                                        }}
                                      >
                                        {inSlot.map((job) => (
                                          <WeekJobChip
                                            key={job.id}
                                            job={job}
                                            customerName={job.customer_name ?? (job.customer_id ? customers.find((c: { id: string }) => c.id === job.customer_id)?.full_name : undefined)}
                                            assignedTechName={job.assigned_user_id ? users.find((u: { id: string }) => u.id === job.assigned_user_id)?.full_name : undefined}
                                            compact
                                            selected={weekRelocateJobId === job.id}
                                            isDragging={activeWeekJobId === job.id}
                                            onMoveToggle={() => setWeekRelocateJobId((cur) => (cur === job.id ? null : job.id))}
                                          />
                                        ))}
                                      </WeekHourDropCell>
                                    )
                                  })}
                                </Fragment>
                              ))}
                            </div>
                          </div>
                        </>
                      )
                    })()}

                    <DragOverlay>
                      {activeWeekJob ? (
                        <WeekJobChip
                          job={activeWeekJob}
                          customerName={activeWeekJob.customer_name ?? (activeWeekJob.customer_id ? customers.find((c: { id: string }) => c.id === activeWeekJob.customer_id)?.full_name : undefined)}
                          assignedTechName={activeWeekJob.assigned_user_id ? users.find((u: { id: string }) => u.id === activeWeekJob.assigned_user_id)?.full_name : undefined}
                          compact={!!activeWeekJob.scheduled_at}
                          isOverlay
                        />
                      ) : null}
                    </DragOverlay>
                  </DndContext>
                )
              })()}
          </div>
          )}
        </div>
      )}

      {view === 'map' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-sm font-medium" style={{ color: 'var(--ms-text-muted)' }}>Range</span>
            <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
              {(['day', 'week', 'month'] as const).map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMapRangeMode(m)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
                  style={{
                    backgroundColor: mapRangeMode === m ? 'var(--ms-surface)' : 'transparent',
                    color: mapRangeMode === m ? 'var(--ms-text)' : 'var(--ms-text-muted)',
                  }}
                >
                  {m === 'day' ? 'Day' : m === 'week' ? 'Week' : 'Month'}
                </button>
              ))}
            </div>
            <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{mapRangeMode === 'day' ? 'Date' : 'Anchor date'}</label>
            <input
              type="date"
              value={dispatchDate}
              onChange={e => setDispatchDate(e.target.value)}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
            />
            {users.length > 1 && (
              <>
                <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Tech</label>
                <Select
                  value={dispatchTechFilter}
                  onChange={e => setDispatchTechFilter(e.target.value)}
                  className="min-w-[160px]"
                  style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
                >
                  <option value="">All techs</option>
                  {users.map((u: { id: string; full_name: string }) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </Select>
              </>
            )}
          </div>
          {dispatchLoading ? <Spinner /> : (
            <MobileServicesMap jobs={dispatchJobs} date={dispatchDate} customers={customers} rangeLabel={mapRangeLabel} />
          )}
        </div>
      )}

      {view === 'planner' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-4">
            <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Date</label>
            <input
              type="date"
              value={dispatchDate}
              onChange={e => setDispatchDate(e.target.value)}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
            />
            {users.length > 1 && (
              <>
                <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Tech</label>
                <Select
                  value={dispatchTechFilter}
                  onChange={e => setDispatchTechFilter(e.target.value)}
                  className="min-w-[160px]"
                  style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
                >
                  <option value="">All techs</option>
                  {users.map((u: { id: string; full_name: string }) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </Select>
              </>
            )}
          </div>
          {dispatchLoading ? (
            <Spinner />
          ) : (
            <>
              <Card className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--ms-text-muted)' }}>
                  {formatDate(dispatchDate)} — {dispatchJobs.length} job{dispatchJobs.length !== 1 ? 's' : ''}
                </h3>
                {dispatchJobs.length === 0 ? (
                  <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>No jobs scheduled for this date.</p>
                ) : (
                  <div className="space-y-3">
                    {[...dispatchJobs]
                      .sort((a: { scheduled_at?: string }, b: { scheduled_at?: string }) => {
                        const ta = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0
                        const tb = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0
                        return ta - tb
                      })
                      .map((job: { id: string; job_number: string; title: string; customer_id: string; customer_name?: string | null; customer_phone?: string | null; scheduled_at?: string; job_address?: string; vehicle_make?: string; vehicle_model?: string }) => {
                        const customer = customers.find((c: { id: string }) => c.id === job.customer_id)
                        const displayName = customer?.full_name ?? job.customer_name ?? '—'
                        const timeStr = job.scheduled_at ? new Date(job.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'
                        return (
                          <div
                            key={job.id}
                            role="button"
                            tabIndex={0}
                            className="flex items-start gap-4 py-3 border-b last:border-b-0 rounded-md px-1 -mx-1 cursor-pointer transition-colors outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                            style={{ borderColor: 'var(--ms-border)' }}
                            onClick={() => setPlannerDetailJobId(job.id)}
                            onKeyDown={e => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                setPlannerDetailJobId(job.id)
                              }
                            }}
                          >
                            <span className="shrink-0 w-12 text-sm font-semibold" style={{ color: 'var(--ms-accent)' }}>{timeStr}</span>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium" style={{ color: 'var(--ms-text)' }}>
                                #{job.job_number} · {job.title}
                              </p>
                              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                                {displayName}
                                {job.vehicle_make || job.vehicle_model ? ` · ${[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}` : ''}
                              </p>
                              {(customer?.phone || job.customer_phone) && (
                                <a
                                  href={`tel:${(customer?.phone || job.customer_phone)!.replace(/\s/g, '')}`}
                                  className="text-xs mt-0.5 flex items-center gap-1 w-fit"
                                  style={{ color: 'var(--ms-accent)' }}
                                  onClick={e => e.stopPropagation()}
                                >
                                  <Phone size={11} /> {customer?.phone || job.customer_phone}
                                </a>
                              )}
                              {job.job_address && (
                                <p className="text-xs mt-0.5 flex items-center gap-1" style={{ color: 'var(--ms-text-mid)' }}>
                                  <MapPin size={12} /> {job.job_address}
                                </p>
                              )}
                            </div>
                            <span
                              className="shrink-0 px-3 py-1.5 rounded text-xs font-medium"
                              style={{ backgroundColor: 'var(--ms-accent)', color: '#2C1810' }}
                            >
                              Details
                            </span>
                          </div>
                        )
                      })}
                  </div>
                )}
              </Card>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Map — where to go</h3>
                <MobileServicesMap jobs={dispatchJobs} date={dispatchDate} customers={customers} />
              </div>
            </>
          )}
        </div>
      )}

      {view === 'reports' && (
        <div className="space-y-6">
          {/* Header row */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Mobile Services Reports</h2>
            <div
              className="inline-flex rounded-lg p-0.5"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
            >
              {([
                { key: 'week' as const, label: 'This week' },
                { key: 'month' as const, label: 'This month' },
                { key: 'all' as const, label: 'Last 90 days' },
              ]).map(p => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setReportPreset(p.key)}
                  className="rounded-md px-4 py-1.5 text-xs font-semibold transition-colors"
                  style={reportPreset === p.key
                    ? { backgroundColor: 'var(--ms-accent)', color: '#fff', border: '1px solid var(--ms-accent)' }
                    : { backgroundColor: 'transparent', color: 'var(--ms-text-muted)', border: '1px solid transparent' }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {reportsError && !reportsLoading && (
            <Card className="p-4">
              <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(reportsErr, 'Could not load reports.')}</p>
            </Card>
          )}

          {reportsLoading ? <Spinner /> : reportsError ? null : autoKeyReports ? (
            <>
              {/* Metric cards */}
              {(() => {
                const topTech = autoKeyReports.jobs_by_tech[0]
                return (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {[
                      {
                        label: 'REVENUE MTD',
                        value: formatCents(autoKeyReports.summary.total_revenue_cents),
                        sub: `${autoKeyReports.summary.mobile_pct ?? 0}% mobile`,
                      },
                      {
                        label: 'JOBS MTD',
                        value: String(autoKeyReports.summary.total_jobs),
                        sub: `${autoKeyReports.summary.mobile_count ?? 0} mobile · ${autoKeyReports.summary.shop_count ?? 0} shop`,
                      },
                      {
                        label: 'AVG PER JOB',
                        value: formatCents(autoKeyReports.summary.avg_job_value_cents),
                        sub: null,
                      },
                      {
                        label: 'TOP TECH',
                        value: topTech?.tech_name ?? '—',
                        sub: topTech ? `${topTech.job_count} jobs · ${formatCents(topTech.revenue_cents)}` : null,
                        large: false,
                      },
                    ].map(card => (
                      <Card key={card.label} className="p-5">
                        <p className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--ms-text-muted)', letterSpacing: '0.08em' }}>{card.label}</p>
                        <p className={card.label === 'TOP TECH' ? 'text-xl font-bold leading-snug' : 'text-2xl font-extrabold'} style={{ color: 'var(--ms-text)' }}>{card.value}</p>
                        {card.sub && <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>{card.sub}</p>}
                      </Card>
                    ))}
                  </div>
                )
              })()}

              {/* Weekly Revenue bar chart + Jobs by Type horizontal bars */}
              <div className="grid gap-6 lg:grid-cols-2">
                <Card className="p-5">
                  <h3 className="text-sm font-semibold mb-5" style={{ color: 'var(--ms-text)' }}>Weekly Revenue</h3>
                  {autoKeyReports.week_on_week.length === 0 ? (
                    <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>No weekly data.</p>
                  ) : (() => {
                    const bars = autoKeyReports.week_on_week.slice(-6)
                    const maxRev = Math.max(...bars.map(b => b.revenue_cents), 1)
                    const CHART_H = 120
                    return (
                      <div className="flex items-end gap-2" style={{ height: CHART_H + 40 }}>
                        {bars.map(b => {
                          const h = Math.round((b.revenue_cents / maxRev) * CHART_H)
                          const isLast = b === bars[bars.length - 1]
                          return (
                            <div key={b.week_label} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                              <span className="text-[10px] font-semibold truncate" style={{ color: 'var(--ms-text)' }}>
                                {b.revenue_cents > 0 ? `$${Math.round(b.revenue_cents / 100 / 1000 * 10) / 10}k` : ''}
                              </span>
                              <div
                                className="w-full rounded-t"
                                style={{
                                  height: Math.max(h, b.revenue_cents > 0 ? 4 : 2),
                                  backgroundColor: isLast ? 'var(--ms-accent)' : 'var(--ms-accent-light)',
                                  minHeight: 2,
                                }}
                                title={`${b.week_label}: ${formatCents(b.revenue_cents)}`}
                              />
                              <span className="text-[10px] truncate w-full text-center" style={{ color: 'var(--ms-text-muted)' }}>{b.week_label}</span>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })()}
                </Card>
                <Card className="p-5">
                  <h3 className="text-sm font-semibold mb-5" style={{ color: 'var(--ms-text)' }}>Jobs by Type</h3>
                  {autoKeyReports.jobs_by_type.length === 0 ? (
                    <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>No data.</p>
                  ) : (() => {
                    const maxJobs = Math.max(...autoKeyReports.jobs_by_type.map(r => r.jobs), 1)
                    return (
                      <div className="space-y-3">
                        {autoKeyReports.jobs_by_type.map(row => (
                          <div key={row.job_type} className="flex items-center gap-3">
                            <span className="text-xs w-36 shrink-0 truncate" style={{ color: 'var(--ms-text)' }}>{row.job_type}</span>
                            <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--ms-bg)' }}>
                              <div
                                className="h-full rounded-full"
                                style={{ width: `${Math.max((row.jobs / maxJobs) * 100, row.jobs > 0 ? 4 : 0)}%`, backgroundColor: 'var(--ms-accent)' }}
                              />
                            </div>
                            <span className="text-xs font-semibold w-12 text-right" style={{ color: 'var(--ms-text-mid)' }}>{row.jobs} jobs</span>
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                </Card>
              </div>

              {/* Technician Leaderboard */}
              {autoKeyReports.jobs_by_tech.length > 0 && (
                <Card className="overflow-hidden">
                  <div className="px-5 py-4 flex items-center gap-2" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    <span style={{ color: 'var(--ms-accent)', fontSize: 16 }}>🏆</span>
                    <h3 className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                      Technician Leaderboard
                    </h3>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
                        {['RANK', 'TECHNICIAN', 'JOBS', 'REVENUE', 'AVG', ...(role === 'owner' || role === 'manager' ? ['COMMISSION'] : [])].map(h => (
                          <th key={h} className="px-5 py-2.5 text-left font-semibold tracking-wider text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {autoKeyReports.jobs_by_tech.map((t, i) => {
                        const initials = t.tech_name.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2)
                        const avgCents = t.job_count > 0 ? Math.round(t.revenue_cents / t.job_count) : 0
                        const commTech = commissionReport?.technicians.find(c => c.user_id === t.tech_id)
                        const rankColors = ['#C07820', '#888', '#B06010']
                        const avatarColors = ['#6B4F1A', '#1A5068', '#1A4A30', '#4A1A68', '#68201A']
                        const avatarBg = avatarColors[i % avatarColors.length]
                        return (
                          <tr key={t.tech_id} style={{ borderBottom: i < autoKeyReports.jobs_by_tech.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                            <td className="px-5 py-4">
                              <span className="font-extrabold text-sm" style={{ color: rankColors[i] ?? 'var(--ms-text-muted)' }}>#{i + 1}</span>
                            </td>
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-3">
                                <div
                                  className="w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0"
                                  style={{ backgroundColor: avatarBg, color: '#fff' }}
                                >
                                  {initials}
                                </div>
                                <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{t.tech_name}</span>
                              </div>
                            </td>
                            <td className="px-5 py-4" style={{ color: 'var(--ms-text)' }}>{t.job_count}</td>
                            <td className="px-5 py-4" style={{ color: 'var(--ms-text)' }}>{formatCents(t.revenue_cents)}</td>
                            <td className="px-5 py-4" style={{ color: 'var(--ms-text-mid)' }}>{formatCents(avgCents)}</td>
                            {(role === 'owner' || role === 'manager') && (
                              <td className="px-5 py-4">
                                {commTech ? (
                                  <span
                                    className="inline-block rounded-md px-3 py-1 text-xs font-bold"
                                    style={{ backgroundColor: 'var(--ms-accent-pop)', color: 'var(--ms-accent)' }}
                                  >
                                    {formatCents(commTech.bonus_payable_cents)}
                                  </span>
                                ) : (
                                  <span style={{ color: 'var(--ms-text-muted)' }}>—</span>
                                )}
                              </td>
                            )}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </Card>
              )}
            </>
          ) : (
            <EmptyState message="No report data. Select a date range." />
          )}
        </div>
      )}
    </div>
  )
}
