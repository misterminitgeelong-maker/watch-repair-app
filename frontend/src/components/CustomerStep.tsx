/**
 * Shared "Step 1 — Customer" subcomponent used by NewJobModal (watch) and
 * NewShoeJobModal (shoe). Both modals previously duplicated the same state +
 * JSX for choosing an existing customer or creating a new one.
 *
 * The hook `useCustomerStep` owns:
 *   - customerMode / selectedCustomerId / newCustomer state
 *   - the /v1/customers list query (queryKey: ['customers'])
 *   - phone-collision detection against existing customers
 *   - submit(): creates a new customer if needed, returns the active id
 *
 * The `<CustomerStep />` component renders the form and wires onChange.
 * Fields can be toggled via `options`:
 *   - includeAddress / includeNotes: watch modal uses both; shoe skips.
 *   - includePhoneMatchHint: watch modal surfaces a duplicate-phone warning.
 */
import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createCustomer,
  listCustomers,
  type Customer,
} from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api'
import { Button, Input, Select, Textarea } from '@/components/ui'

export interface NewCustomerDraft {
  full_name: string
  email: string
  phone: string
  address: string
  notes: string
}

const EMPTY_DRAFT: NewCustomerDraft = {
  full_name: '',
  email: '',
  phone: '',
  address: '',
  notes: '',
}

export interface UseCustomerStepResult {
  customerMode: 'existing' | 'new'
  setCustomerMode: (m: 'existing' | 'new') => void
  selectedCustomerId: string
  setSelectedCustomerId: (id: string) => void
  newCustomer: NewCustomerDraft
  setNewCustomerField: (k: keyof NewCustomerDraft, v: string) => void
  createdCustomerId: string
  phoneMatch: Customer | null
  customers: Customer[] | undefined
  /** The id the outer flow should use once the step is done. */
  activeCustomerId: string
  /**
   * Run step-1 submission: create the customer if in 'new' mode, otherwise
   * validate a selection. Returns the active customer id or null on error.
   * Caller is responsible for surfacing errors.
   */
  submit: () => Promise<{ ok: true; customerId: string } | { ok: false; error: string }>
}

/** Shared hook — both modals call this before rendering Step 1. */
export function useCustomerStep(opts?: {
  preselectedCustomerId?: string
  enableCustomersQuery?: boolean
}): UseCustomerStepResult {
  const qc = useQueryClient()
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [selectedCustomerId, setSelectedCustomerId] = useState(opts?.preselectedCustomerId ?? '')
  const [draft, setDraft] = useState<NewCustomerDraft>(EMPTY_DRAFT)
  const [createdCustomerId, setCreatedCustomerId] = useState('')
  const [phoneMatch, setPhoneMatch] = useState<Customer | null>(null)

  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then((r) => r.data),
    enabled: opts?.enableCustomersQuery ?? true,
  })

  const setNewCustomerField = (k: keyof NewCustomerDraft, v: string) => {
    setDraft((prev) => ({ ...prev, [k]: v }))
    if (k === 'phone' && customers) {
      const digits = v.replace(/\D/g, '')
      if (digits.length >= 6) {
        const match = customers.find(
          (c: Customer) => c.phone && c.phone.replace(/\D/g, '') === digits,
        )
        setPhoneMatch(match ?? null)
      } else {
        setPhoneMatch(null)
      }
    }
  }

  async function submit(): Promise<
    { ok: true; customerId: string } | { ok: false; error: string }
  > {
    if (customerMode === 'new') {
      if (!draft.full_name.trim()) {
        return { ok: false, error: 'Customer name is required.' }
      }
      try {
        const { data } = await createCustomer(draft)
        setCreatedCustomerId(data.id)
        qc.invalidateQueries({ queryKey: ['customers'] })
        return { ok: true, customerId: data.id }
      } catch (err) {
        return { ok: false, error: getApiErrorMessage(err, 'Failed to create customer.') }
      }
    }
    if (!selectedCustomerId) {
      return { ok: false, error: 'Please select a customer.' }
    }
    return { ok: true, customerId: selectedCustomerId }
  }

  const activeCustomerId = useMemo(
    () => createdCustomerId || selectedCustomerId,
    [createdCustomerId, selectedCustomerId],
  )

  return {
    customerMode,
    setCustomerMode,
    selectedCustomerId,
    setSelectedCustomerId,
    newCustomer: draft,
    setNewCustomerField,
    createdCustomerId,
    phoneMatch,
    customers,
    activeCustomerId,
    submit,
  }
}

// ── Component ──────────────────────────────────────────────────────────────

export interface CustomerStepProps {
  state: UseCustomerStepResult
  /** When true (watch modal) show address + notes fields. Default false. */
  includeAddressAndNotes?: boolean
  /** When true (watch modal) surface a "this phone already exists" hint. */
  includePhoneMatchHint?: boolean
  /** Error banner above the Next button. */
  error?: string | null
  /** Primary button label; usually 'Next →' or 'Continue'. */
  primaryLabel?: string
  /** Invoked when the user clicks the primary button. */
  onNext: () => void
  /** Optional cancel button click handler (watch modal wires it; shoe doesn't). */
  onCancel?: () => void
  /** Disables the primary button during submission. */
  loading?: boolean
  /** Override 'Full Name' autofocus (default: on, matches old NewJobModal). */
  autoFocus?: boolean
}

export function CustomerStep({
  state,
  includeAddressAndNotes = false,
  includePhoneMatchHint = false,
  error,
  primaryLabel = 'Next →',
  onNext,
  onCancel,
  loading = false,
  autoFocus = true,
}: CustomerStepProps) {
  const s = state
  return (
    <div className="space-y-3">
      <div className="flex gap-2 mb-1">
        <button
          type="button"
          onClick={() => s.setCustomerMode('existing')}
          className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
          style={
            s.customerMode === 'existing'
              ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
              : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
          }
        >
          Existing Customer
        </button>
        <button
          type="button"
          onClick={() => s.setCustomerMode('new')}
          className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
          style={
            s.customerMode === 'new'
              ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
              : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
          }
        >
          New Customer
        </button>
      </div>

      {s.customerMode === 'existing' ? (
        <Select
          label="Select Customer"
          value={s.selectedCustomerId}
          onChange={(e) => s.setSelectedCustomerId(e.target.value)}
        >
          <option value="">Choose…</option>
          {(s.customers ?? []).map((c: Customer) => (
            <option key={c.id} value={c.id}>
              {c.full_name}
              {c.phone ? ` · ${c.phone}` : ''}
            </option>
          ))}
        </Select>
      ) : (
        <>
          <Input
            label="Full Name *"
            value={s.newCustomer.full_name}
            onChange={(e) => s.setNewCustomerField('full_name', e.target.value)}
            placeholder="Jane Smith"
            autoFocus={autoFocus}
          />
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Phone"
              value={s.newCustomer.phone}
              onChange={(e) => s.setNewCustomerField('phone', e.target.value)}
              placeholder="0412 345 678"
            />
            <Input
              label="Email"
              type="email"
              value={s.newCustomer.email}
              onChange={(e) => s.setNewCustomerField('email', e.target.value)}
              placeholder="jane@example.com"
            />
          </div>
          {includePhoneMatchHint && s.phoneMatch && (
            <div className="rounded bg-yellow-100 border border-yellow-300 px-3 py-2 text-sm mt-2 flex items-center gap-2">
              <span>Existing customer found with this phone:</span>
              <span className="font-semibold">{s.phoneMatch.full_name}</span>
              <Button
                variant="secondary"
                onClick={() => {
                  s.setCustomerMode('existing')
                  s.setSelectedCustomerId(s.phoneMatch!.id)
                }}
              >
                Use
              </Button>
            </div>
          )}
          {includeAddressAndNotes && (
            <>
              <Input
                label="Address"
                value={s.newCustomer.address}
                onChange={(e) => s.setNewCustomerField('address', e.target.value)}
                placeholder="Unit 5/36 Grange Rd, Toorak 3142"
              />
              <Textarea
                label="Notes"
                value={s.newCustomer.notes}
                onChange={(e) => s.setNewCustomerField('notes', e.target.value)}
                rows={2}
                placeholder="VIP, allergic to…"
              />
            </>
          )}
        </>
      )}

      {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

      <div className={onCancel ? 'flex justify-end gap-2 pt-2' : 'pt-2'}>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button
          onClick={onNext}
          disabled={loading}
          className={onCancel ? undefined : 'w-full'}
        >
          {loading ? 'Saving…' : primaryLabel}
        </Button>
      </div>
    </div>
  )
}
