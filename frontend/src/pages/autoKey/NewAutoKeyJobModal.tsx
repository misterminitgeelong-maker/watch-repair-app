import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Minus } from 'lucide-react'
import {
  createAutoKeyJob,
  createCustomer,
  getApiErrorMessage,
  getAutoKeyQuoteSuggestions,
  listAutoKeyJobs,
  listCustomerAccounts,
  listCustomers,
  listUsers,
  searchVehicleKeySpecs,
  MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS,
  type CustomerAccount,
  type JobStatus,
  type MobileServicesPricingSelection,
  type VehicleKeySpecMatch,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { AddressAutocompleteInput } from '@/components/AddressAutocompleteInput'
import PricingSelector from '@/components/PricingSelector'
import { AklComplexityPill } from '@/components/auto-key/AklComplexityPill'
import { Button, Input, Modal, Select, Textarea } from '@/components/ui'
import { AUTO_KEY_JOB_TYPES, MOBILE_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { STATUS_LABELS } from '@/lib/utils'
import { STATUSES, formatCents } from './dispatchHelpers'
import { CustomerSearchSelect } from './CustomerSearchSelect'

export function NewAutoKeyJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { hasFeature } = useAuth()
  const [error, setError] = useState('')
  const [step, setStep] = useState<1 | 2>(1)
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
  const [applySuggestedQuote, setApplySuggestedQuote] = useState(true)
  const [sendBookingSms, setSendBookingSms] = useState(false)
  const [showPricingSelector, setShowPricingSelector] = useState(false)
  const [pricingSelection, setPricingSelection] = useState<MobileServicesPricingSelection | null>(null)
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
  const additionalPresets = extraServices.map(s => s.preset.trim()).filter(Boolean)
  const { data: quoteSuggestion, isFetching: quoteSuggestionLoading } = useQuery({
    queryKey: ['auto-key-quote-suggestions', form.job_type, suggestionQty, pricingTier, additionalPresets],
    queryFn: () =>
      getAutoKeyQuoteSuggestions({
        job_type: form.job_type.trim() || undefined,
        key_quantity: suggestionQty,
        pricing_tier: pricingTier,
        additional_presets: additionalPresets.length ? additionalPresets : undefined,
      }).then(r => r.data),
  })

  useEffect(() => {
    if (!applySuggestedQuote || !quoteSuggestion || pricingSelection) return
    const dollars = (quoteSuggestion.total_cents / 100).toFixed(2)
    setForm(f => ({ ...f, cost: dollars }))
  }, [applySuggestedQuote, quoteSuggestion?.total_cents, pricingSelection])

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
        pricing_ref_id: pricingSelection?.pricing_ref_id,
        pricing_type: pricingSelection?.pricing_type,
        quoted_price: pricingSelection?.quoted_price,
        callout_inclusive: pricingSelection?.callout_inclusive,
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
      <div className="relative">
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
            <AddressAutocompleteInput
              label={MOBILE_JOB_TYPES.has(form.job_type) ? 'Job address *' : 'Job address'}
              value={form.job_address}
              onChange={val => setForm(f => ({ ...f, job_address: val }))}
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
              <div>
                <Input label="Cost ($)" type="number" step="0.01" value={form.cost} onChange={e => {
                  setPricingSelection(null)
                  setForm(f => ({ ...f, cost: e.target.value }))
                }} />
                <Button
                  type="button"
                  variant="secondary"
                  className="mt-1.5 w-full text-sm"
                  onClick={() => setShowPricingSelector(true)}
                >
                  Browse pricing catalogue
                </Button>
                {pricingSelection && (
                  <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                    From catalogue: {pricingSelection.label ?? pricingSelection.pricing_type}
                    {pricingSelection.callout_inclusive ? ' · Callout incl.' : ' · + Callout'}
                  </p>
                )}
              </div>
            </div>
            <Input label="Salesperson" value={form.salesperson} onChange={e => setForm(f => ({ ...f, salesperson: e.target.value }))} />
          </>
        )}

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex gap-2 pt-2">
          {step === 1 ? (
            <>
              <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
              <Button className="flex-1" type="button" onClick={() => {
                setError('')
                if (customerMode === 'existing' && !form.customer_id) {
                  setError('Please select a customer.')
                  return
                }
                if (customerMode === 'new' && !newCustomer.full_name.trim()) {
                  setError('Customer name is required.')
                  return
                }
                if (MOBILE_JOB_TYPES.has(form.job_type) && !form.job_address.trim()) {
                  setError('Address is required for this job type.')
                  return
                }
                setStep(2)
              }}>Next →</Button>
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
        <PricingSelector
          open={showPricingSelector}
          onClose={() => setShowPricingSelector(false)}
          initialMake={form.vehicle_make}
          onConfirm={(selection) => {
            setPricingSelection(selection)
            setApplySuggestedQuote(false)
            setForm(f => ({ ...f, cost: selection.quoted_price.toFixed(2) }))
          }}
        />
      </div>
    </Modal>
  )
}
