import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Minus, X, CreditCard } from 'lucide-react'
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
import { dollarsToCents, computeGstAmounts } from '@/lib/money'
import { CustomerSearchSelect } from '@/components/CustomerSearchSelect'
import PricingSelector from '@/components/PricingSelector'
import { invalidateAutoKeyJobCollections } from '@/lib/autoKeyJobQueries'
import { DEFAULT_POS_CATEGORIES, quickItemsForCategories } from './posQuickItems'

interface CartLine {
  id: string
  description: string
  quantity: number
  unit_price_cents: number
}

export function POSView({ customers, customerAccounts, onComplete, initialJobId }: { customers: Customer[]; customerAccounts: CustomerAccount[]; onComplete: () => void; initialJobId?: string | null }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [customerId, setCustomerId] = useState('')
  const [customerAccountId, setCustomerAccountId] = useState('')
  const [linkToJobId, setLinkToJobId] = useState('')
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '' })
  const [cart, setCart] = useState<CartLine[]>([])
  const [showPricingSelector, setShowPricingSelector] = useState(false)
  const { data: catalogueMeta } = useQuery({
    queryKey: ['mobile-services-pricing', 'meta'],
    queryFn: () => getMobileServicesPricingMeta().then(r => r.data),
    staleTime: 60_000,
  })
  const quickItems = quickItemsForCategories(catalogueMeta?.enabled_categories ?? DEFAULT_POS_CATEGORIES)
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
  const [customDesc, setCustomDesc] = useState('')
  const [customPrice, setCustomPrice] = useState('')
  const [error, setError] = useState('')
  const [successJobId, setSuccessJobId] = useState<string | null>(null)
  const [gstEnabled, setGstEnabled] = useState(true)
  const [gstInclusive, setGstInclusive] = useState(true)

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

      let job: { id: string }
      if (linkToJobId) {
        job = { id: linkToJobId }
        const quote = await createAutoKeyQuote(linkToJobId, {
          line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
          gst_enabled: gstEnabled,
          gst_inclusive: gstInclusive,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(linkToJobId, quote.id)
        await updateAutoKeyJobStatus(linkToJobId, 'work_completed')
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
          gst_enabled: gstEnabled,
          gst_inclusive: gstInclusive,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(job.id, quote.id)
        await updateAutoKeyJobStatus(job.id, 'work_completed')
      }

      return { job }
    },
    onError: (err: unknown) => {
      setError(
        getApiErrorMessage(
          err,
          'POS sale could not be completed. Check Mobile Services jobs and invoices — a partial sale may have been saved.',
        ),
      )
    },
    onSuccess: ({ job }) => {
      invalidateAutoKeyJobCollections(qc)
      qc.invalidateQueries({ queryKey: ['auto-key-job', job.id] })
      setCart([])
      setCustomerId('')
      setCustomerAccountId('')
      setLinkToJobId('')
      setNewCustomer({ full_name: '', email: '', phone: '' })
      setSuccessJobId(job.id)
      onComplete()
    },
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
    <div className="relative grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        {initialJob && (
          <Card className="p-4" style={{ borderColor: 'var(--ms-accent)' }}>
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--ms-accent)' }}>Linked job</p>
            <p className="text-sm font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>#{initialJob.job_number} · {initialJob.title}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>Customer and job are preselected. Add the final work performed, then complete the sale.</p>
          </Card>
        )}
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
          <div className="flex flex-wrap gap-2 mb-4">
            {quickItems.map(({ label, desc, price }) => (
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
                  <button type="button" onClick={() => removeFromCart(line.id)} className="w-7 h-7 rounded flex items-center justify-center" style={{ color: 'var(--ms-error)' }}><X size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="border-t pt-4" style={{ borderColor: 'var(--ms-border)' }}>
          <label className="flex items-center gap-2 text-sm mb-2" style={{ color: 'var(--ms-text)' }}>
            <input type="checkbox" checked={gstEnabled} onChange={e => setGstEnabled(e.target.checked)} />
            Apply GST (10%)
          </label>
          {gstEnabled && (
            <div className="flex gap-4 pl-6 text-sm mb-2" style={{ color: 'var(--ms-text-mid)' }}>
              <label className="flex items-center gap-1.5">
                <input type="radio" name="gst-mode-pos" checked={gstInclusive} onChange={() => setGstInclusive(true)} />
                Included
              </label>
              <label className="flex items-center gap-1.5">
                <input type="radio" name="gst-mode-pos" checked={!gstInclusive} onChange={() => setGstInclusive(false)} />
                Add on top
              </label>
            </div>
          )}
          <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>Subtotal</span><span style={{ color: 'var(--ms-text)' }}>${(subtotal / 100).toFixed(2)}</span></div>
          {tax > 0 && <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--ms-text-muted)' }}>GST</span><span style={{ color: 'var(--ms-text)' }}>${(tax / 100).toFixed(2)}</span></div>}
          <div className="flex justify-between text-lg font-bold mt-2" style={{ color: 'var(--ms-accent)' }}><span>Total</span><span>${(total / 100).toFixed(2)}</span></div>
        </div>
        {error && <p className="text-sm mt-3" style={{ color: 'var(--ms-error)' }}>{error}</p>}
        <Button
          className="w-full mt-4"
          onClick={() => completeMut.mutate()}
          disabled={completeMut.isPending || cart.length === 0}
        >
          <CreditCard size={16} />
          {completeMut.isPending ? 'Processing…' : 'Complete sale'}
        </Button>
      </Card>

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
