import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Minus, Plus, Trash2, CreditCard, FileText, Search } from 'lucide-react'
import {
  createAutoKeyInvoiceFromQuote,
  createAutoKeyJob,
  createAutoKeyQuote,
  createCustomer,
  getAutoKeyJob,
  getApiErrorMessage,
  getMobileServicesPricingMeta,
  listAutoKeyJobs,
  updateAutoKeyJobStatus,
  type Customer,
  type CustomerAccount,
  type MobileServicesPricingSelection,
} from '@/lib/api'
import { Card, Button, Input, Select } from '@/components/ui'
import MobileStickyBar, { MobileStickyBarSpacer } from '@/components/mobile/MobileStickyBar'
import { dollarsToCents, computeGstAmounts } from '@/lib/money'
import { CustomerSearchSelect } from '@/components/CustomerSearchSelect'
import PricingSelector from '@/components/PricingSelector'
import { invalidateAutoKeyJobCollections } from '@/lib/autoKeyJobQueries'
import { DEFAULT_POS_CATEGORIES, quickItemsForCategories, filterQuickItems } from './posQuickItems'
import { isPosQuoteMode, type PosCheckoutMode } from './posMode'

interface CartLine {
  id: string
  description: string
  quantity: number
  unit_price_cents: number
}

export function POSView({
  customers,
  customerAccounts,
  onComplete,
  initialJobId,
  initialMode,
  onModeChange,
}: {
  customers: Customer[]
  customerAccounts: CustomerAccount[]
  onComplete: () => void
  initialJobId?: string | null
  initialMode?: PosCheckoutMode | null
  onModeChange?: (mode: PosCheckoutMode) => void
}) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [customerId, setCustomerId] = useState('')
  const [customerAccountId, setCustomerAccountId] = useState('')
  const [linkToJobId, setLinkToJobId] = useState('')
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '' })
  const [cart, setCart] = useState<CartLine[]>([])
  const [modeOverride, setModeOverride] = useState<PosCheckoutMode | null>(null)
  const [showPricingSelector, setShowPricingSelector] = useState(false)
  const { data: catalogueMeta } = useQuery({
    queryKey: ['mobile-services-pricing', 'meta'],
    queryFn: () => getMobileServicesPricingMeta().then(r => r.data),
    staleTime: 60_000,
  })
  const quickItems = quickItemsForCategories(catalogueMeta?.enabled_categories ?? DEFAULT_POS_CATEGORIES)
  const [itemQuery, setItemQuery] = useState('')
  const visibleQuickItems = useMemo(() => filterQuickItems(quickItems, itemQuery), [quickItems, itemQuery])
  const { data: initialJob } = useQuery({
    queryKey: ['auto-key-job', initialJobId],
    queryFn: () => getAutoKeyJob(initialJobId!).then(r => r.data),
    enabled: !!initialJobId,
  })

  useEffect(() => {
    if (!initialJob) return
    setCustomerMode('existing')
    setCustomerId(initialJob.customer_id)
    setLinkToJobId(initialJob.id)
  }, [initialJob])

  const { data: activeJobsForCustomer = [] } = useQuery({
    queryKey: ['auto-key-jobs', 'active', customerId],
    queryFn: () => listAutoKeyJobs({ customer_id: customerId, active_only: true }).then(r => r.data),
    enabled: !!customerId && customerMode === 'existing',
  })
  const linkableJobs = initialJob && initialJob.customer_id === customerId && !activeJobsForCustomer.some(job => job.id === initialJob.id)
    ? [initialJob, ...activeJobsForCustomer]
    : activeJobsForCustomer
  const linkedJob = [initialJob, ...activeJobsForCustomer].find(job => job && job.id === linkToJobId) ?? null
  const quoteMode = isPosQuoteMode({ explicitMode: modeOverride ?? initialMode, job: linkedJob })

  useEffect(() => {
    setModeOverride(null)
  }, [initialMode, initialJobId])
  const [customDesc, setCustomDesc] = useState('')
  const [customPrice, setCustomPrice] = useState('')
  const [error, setError] = useState('')
  const [successJobId, setSuccessJobId] = useState<string | null>(null)
  const [gstEnabled, setGstEnabled] = useState(true)
  const [gstInclusive, setGstInclusive] = useState(true)

  const cartCount = cart.reduce((n, l) => n + l.quantity, 0)
  const enteredCents = cart.reduce((s, l) => s + l.quantity * l.unit_price_cents, 0)
  const { subtotalCents: subtotal, taxCents: tax, totalCents: total } = computeGstAmounts(enteredCents, gstEnabled, gstInclusive)

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

      const accountId = customerAccountId && customerAccounts.some((a: CustomerAccount) => a.id === customerAccountId && (a.customer_ids ?? []).includes(cid))
        ? customerAccountId
        : undefined

      const quotePayload = {
        line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
        gst_enabled: gstEnabled,
        gst_inclusive: gstInclusive,
      }

      let job: { id: string }
      if (linkToJobId) {
        job = { id: linkToJobId }
      } else {
        job = await createAutoKeyJob({
          customer_id: cid,
          customer_account_id: accountId || undefined,
          title: `${quoteMode ? 'Quote' : 'POS sale'} ${new Date().toLocaleDateString()}`,
          key_quantity: 1,
          programming_status: 'not_required',
          priority: 'normal',
          status: 'awaiting_quote',
          deposit_cents: 0,
          cost_cents: total,
        }).then(r => r.data)
      }

      const quote = await createAutoKeyQuote(job.id, quotePayload).then(r => r.data)
      if (!quoteMode) {
        await createAutoKeyInvoiceFromQuote(job.id, quote.id)
        await updateAutoKeyJobStatus(job.id, 'work_completed')
      }

      return { job, mode: quoteMode ? 'quote' as const : 'sale' as const }
    },
    onError: (err: unknown) => {
      setError(
        getApiErrorMessage(
          err,
          quoteMode
            ? 'Quote could not be saved. Check the job Financial tab — a draft may already be there.'
            : 'POS sale could not be completed. Check Mobile Services jobs and invoices — a partial sale may have been saved.',
        ),
      )
    },
    onSuccess: ({ job, mode }) => {
      invalidateAutoKeyJobCollections(qc)
      qc.invalidateQueries({ queryKey: ['auto-key-job', job.id] })
      qc.invalidateQueries({ queryKey: ['auto-key-quotes', job.id] })
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', job.id] })
      onComplete()
      if (mode === 'quote') {
        navigate(`/auto-key/${job.id}?tab=financial`)
        return
      }
      setCart([])
      setCustomerId('')
      setCustomerAccountId('')
      setLinkToJobId('')
      setNewCustomer({ full_name: '', email: '', phone: '' })
      setSuccessJobId(job.id)
    },
  })

  const setCheckoutMode = (mode: PosCheckoutMode) => {
    setModeOverride(mode)
    onModeChange?.(mode)
  }

  const submitLabel = quoteMode ? 'Complete quote' : 'Complete sale'
  const submitIcon = quoteMode ? <FileText size={16} /> : <CreditCard size={16} />

  if (successJobId) {
    return (
      <Card className="p-8 text-center">
        <p className="text-lg font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>Sale complete</p>
        <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
          Invoice created (unpaid). Send to customer via email or SMS, or record payment on the job.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center sm:flex-wrap">
          <Button variant="secondary" className="w-full sm:w-auto" onClick={() => setSuccessJobId(null)}>New sale</Button>
          <Button className="w-full sm:w-auto" onClick={() => { setSuccessJobId(null); navigate(`/auto-key/${successJobId}`) }}>
            View job &amp; record payment
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="relative grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--ms-text)' }}>
            {quoteMode ? 'Create quote' : 'Point of sale'}
          </h2>
          <div
            role="group"
            aria-label="Checkout mode"
            className="inline-flex rounded-lg p-0.5"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
          >
            <button
              type="button"
              aria-pressed={quoteMode}
              onClick={() => setCheckoutMode('quote')}
              className="min-h-11 rounded-md px-3 text-sm font-semibold sm:min-h-9"
              style={quoteMode
                ? { backgroundColor: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }
                : { color: 'var(--ms-text-muted)' }}
            >
              Quote
            </button>
            <button
              type="button"
              aria-pressed={!quoteMode}
              onClick={() => setCheckoutMode('sale')}
              className="min-h-11 rounded-md px-3 text-sm font-semibold sm:min-h-9"
              style={!quoteMode
                ? { backgroundColor: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }
                : { color: 'var(--ms-text-muted)' }}
            >
              Sale
            </button>
          </div>
        </div>
        {initialJob && (
          <Card className="p-4" style={{ borderColor: 'var(--ms-accent)' }}>
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--ms-accent)' }}>Linked job</p>
            <p className="text-sm font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>#{initialJob.job_number} · {initialJob.title}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
              {quoteMode
                ? 'Customer and job are preselected. Add the quoted work, then complete the quote. This saves a quote — it does not take payment or mark the job sold.'
                : 'Customer and job are preselected. Add the final work performed, then complete the sale.'}
            </p>
          </Card>
        )}
        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Customer</h3>
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setCustomerMode('existing')}
              className={`min-h-11 flex-1 rounded border py-2 text-sm font-medium sm:min-h-0 ${customerMode === 'existing' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
              style={customerMode === 'existing' ? { backgroundColor: 'rgba(245,158,11,0.2)', borderColor: 'var(--ms-accent)' } : {}}
            >Existing</button>
            <button
              onClick={() => setCustomerMode('new')}
              className={`min-h-11 flex-1 rounded border py-2 text-sm font-medium sm:min-h-0 ${customerMode === 'new' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
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
                    onChange={e => { setCustomerAccountId(e.target.value); setGstInclusive(!e.target.value) }}
                  >
                    <option value="">Personal / no B2B</option>
                    {customerAccounts
                      .filter((a: CustomerAccount) => (a.customer_ids ?? []).includes(customerId))
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
                    {linkableJobs.map((j: { id: string; job_number: string; vehicle_make?: string | null; vehicle_model?: string | null }) => (
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
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Add items</h3>
            <Button type="button" variant="secondary" onClick={() => setShowPricingSelector(true)}>
              Price by manufacturer
            </Button>
          </div>
          <div className="relative mb-3">
            <Search
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--ms-text-muted)' }}
            />
            <Input
              type="search"
              aria-label="Search items"
              placeholder="Search items…"
              className="pl-9"
              value={itemQuery}
              onChange={e => setItemQuery(e.target.value)}
            />
          </div>
          {/* One tappable card per item on a phone; the desktop pill row is
              kept from sm: up where the labels fit side by side. */}
          <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {visibleQuickItems.map(({ label, desc, price }) => (
              <button
                key={label}
                type="button"
                onClick={() => addToCart(desc, price)}
                className="flex min-h-14 w-full items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-left transition-colors"
                style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">{label}</span>
                  <span className="block truncate text-xs" style={{ color: 'var(--ms-text-muted)' }}>{desc}</span>
                </span>
                <span className="shrink-0 text-sm font-bold tabular-nums" style={{ color: 'var(--ms-accent)' }}>
                  ${(price / 100).toFixed(2)}
                </span>
              </button>
            ))}
          </div>
          {visibleQuickItems.length === 0 && (
            <p className="mb-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              No catalogue item matches “{itemQuery}”. Add it as a custom line below.
            </p>
          )}
          {/* Stacks on a phone so the description keeps full width and the
              price field is not squeezed to a few characters. */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_7rem_auto]">
            <Input
              aria-label="Custom item description"
              placeholder="Description"
              value={customDesc}
              onChange={e => setCustomDesc(e.target.value)}
            />
            <Input
              type="number"
              step="0.01"
              min="0"
              inputMode="decimal"
              aria-label="Custom item price"
              placeholder="Price"
              value={customPrice}
              onChange={e => setCustomPrice(e.target.value)}
            />
            <Button
              variant="secondary"
              className="w-full sm:w-auto"
              onClick={() => {
                const cents = dollarsToCents(customPrice)
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

      <Card className="p-5 h-fit" id="pos-cart">
        <h3 className="text-sm font-semibold uppercase tracking-wide mb-4 flex items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
          <ShoppingCart size={16} /> Cart
        </h3>
        {cart.length === 0 ? (
          <p className="text-sm py-6 text-center" style={{ color: 'var(--ms-text-muted)' }}>Cart empty. Add items above.</p>
        ) : (
          <div className="space-y-3 mb-4">
            {cart.map(line => (
              <div key={line.id} className="border-b py-2" style={{ borderColor: 'var(--ms-border)' }}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{line.description}</p>
                    <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                      ${(line.unit_price_cents / 100).toFixed(2)} × {line.quantity}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold tabular-nums" style={{ color: 'var(--ms-text)' }}>
                    ${((line.unit_price_cents * line.quantity) / 100).toFixed(2)}
                  </p>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  {/* Quantity controls grouped on the left; remove is pushed to
                      the far edge so a mis-tap does not delete the line. */}
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={`Decrease quantity of ${line.description}`}
                      onClick={() => updateQty(line.id, line.quantity - 1)}
                      className="flex h-11 w-11 items-center justify-center rounded-lg border sm:h-8 sm:w-8"
                      style={{ backgroundColor: 'var(--ms-bg)', borderColor: 'var(--ms-border)', color: 'var(--ms-text)' }}
                    >
                      <Minus size={16} />
                    </button>
                    <span
                      className="w-9 text-center text-sm font-semibold tabular-nums"
                      aria-label={`Quantity ${line.quantity}`}
                      style={{ color: 'var(--ms-text)' }}
                    >
                      {line.quantity}
                    </span>
                    <button
                      type="button"
                      aria-label={`Increase quantity of ${line.description}`}
                      onClick={() => updateQty(line.id, line.quantity + 1)}
                      className="flex h-11 w-11 items-center justify-center rounded-lg border sm:h-8 sm:w-8"
                      style={{ backgroundColor: 'var(--ms-bg)', borderColor: 'var(--ms-border)', color: 'var(--ms-text)' }}
                    >
                      <Plus size={16} />
                    </button>
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${line.description}`}
                    onClick={() => removeFromCart(line.id)}
                    className="flex h-11 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold sm:h-8"
                    style={{ color: 'var(--ms-error)', backgroundColor: 'transparent' }}
                  >
                    <Trash2 size={15} />
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="border-t pt-4" style={{ borderColor: 'var(--ms-border)' }}>
          <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0 sm:mb-2" style={{ color: 'var(--ms-text)' }}>
            <input type="checkbox" className="h-5 w-5 sm:h-4 sm:w-4" checked={gstEnabled} onChange={e => setGstEnabled(e.target.checked)} />
            Apply GST (10%)
          </label>
          {gstEnabled && (
            <div className="flex flex-col pl-6 text-sm sm:mb-2 sm:flex-row sm:gap-4" style={{ color: 'var(--ms-text-mid)' }}>
              <label className="flex min-h-11 items-center gap-2 sm:min-h-0 sm:gap-1.5">
                <input type="radio" className="h-5 w-5 sm:h-4 sm:w-4" name="gst-mode-pos" checked={gstInclusive} onChange={() => setGstInclusive(true)} />
                Included
              </label>
              <label className="flex min-h-11 items-center gap-2 sm:min-h-0 sm:gap-1.5">
                <input type="radio" className="h-5 w-5 sm:h-4 sm:w-4" name="gst-mode-pos" checked={!gstInclusive} onChange={() => setGstInclusive(false)} />
                Add on top
              </label>
            </div>
          )}
          <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>Subtotal</span><span style={{ color: 'var(--ms-text)' }}>${(subtotal / 100).toFixed(2)}</span></div>
          {tax > 0 && <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>GST</span><span style={{ color: 'var(--ms-text)' }}>${(tax / 100).toFixed(2)}</span></div>}
          <div className="flex justify-between text-lg font-bold mt-2" style={{ color: 'var(--ms-accent)' }}><span>Total</span><span>${(total / 100).toFixed(2)}</span></div>
        </div>
        {error && <p role="alert" className="text-sm mt-3" style={{ color: 'var(--ms-error)' }}>{error}</p>}
        {/* Phones use the sticky checkout bar below instead, so the action is
            never stranded at the bottom of a long page. */}
        <Button
          className="mt-4 hidden w-full md:inline-flex"
          onClick={() => completeMut.mutate()}
          disabled={completeMut.isPending || cart.length === 0}
        >
          {submitIcon}
          {completeMut.isPending ? 'Processing…' : submitLabel}
        </Button>
      </Card>

      <MobileStickyBarSpacer />

      {/* Phone checkout: the running total and the one primary action stay in
          reach no matter how far down the item list the user has scrolled. It
          is a single compact row, so it never covers a form field, and it
          steps aside entirely while the keyboard is up. */}
      <MobileStickyBar label="Cart total and checkout">
        {error && (
          <p role="alert" className="mb-2 text-xs" style={{ color: 'var(--ms-error)' }}>
            {error}
          </p>
        )}
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="flex min-h-11 flex-1 items-center justify-between gap-2 rounded-lg px-3 text-left"
            style={{ backgroundColor: 'var(--ms-bg)' }}
            onClick={() => document.getElementById('pos-cart')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          >
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              {cartCount === 0 ? 'Cart empty' : `${cartCount} item${cartCount === 1 ? '' : 's'}`}
            </span>
            <span className="text-base font-bold tabular-nums" style={{ color: 'var(--ms-accent)' }}>
              ${(total / 100).toFixed(2)}
            </span>
          </button>
          <Button
            className="shrink-0"
            onClick={() => completeMut.mutate()}
            disabled={completeMut.isPending || cart.length === 0}
          >
            {submitIcon}
            {completeMut.isPending ? 'Processing…' : submitLabel}
          </Button>
        </div>
      </MobileStickyBar>

      <PricingSelector
        open={showPricingSelector}
        onClose={() => setShowPricingSelector(false)}
        onConfirm={(selection: MobileServicesPricingSelection) => {
          addToCart(selection.label || 'Vehicle key pricing', Math.round(selection.quoted_price * 100))
          setShowPricingSelector(false)
        }}
      />
    </div>
  )
}
