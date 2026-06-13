import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createAutoKeyQuote, getApiErrorMessage } from '@/lib/api'
import { QUOTE_PRESETS } from '@/lib/autoKeyJobTypes'
import { dollarsToCents } from '@/lib/money'
import { Modal, Input, Button } from '@/components/ui'

interface QuoteLineItemDraft { description: string; quantity: string; unitPrice: string }

/**
 * Create a mobile-services quote for an auto-key job: one-tap preset bundles,
 * editable line items, GST, and live total. Self-contained modal.
 */
export function CreateQuoteModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [items, setItems] = useState<QuoteLineItemDraft[]>([{ description: '', quantity: '1', unitPrice: '' }])
  const [tax, setTax] = useState('0.00')

  const addPreset = (p: typeof QUOTE_PRESETS[number]) => {
    setItems(prev => {
      // One-tap: replace a blank first row, otherwise append so bundles stack.
      if (prev.length === 1 && !prev[0].description && !prev[0].unitPrice) {
        return [{ description: p.description, quantity: '1', unitPrice: String(p.price) }]
      }
      return [...prev, { description: p.description, quantity: '1', unitPrice: String(p.price) }]
    })
  }

  const updateItem = (i: number, field: keyof QuoteLineItemDraft, val: string) =>
    setItems(prev => prev.map((item, idx) => (idx === i ? { ...item, [field]: val } : item)))
  const removeItem = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i))
  const addBlankItem = () => setItems(prev => [...prev, { description: '', quantity: '1', unitPrice: '' }])

  const subtotal = items.reduce((sum, item) => sum + parseFloat(item.unitPrice || '0') * parseFloat(item.quantity || '1'), 0)
  const taxAmt = parseFloat(tax || '0')
  const total = subtotal + taxAmt

  const quoteMut = useMutation({
    mutationFn: () =>
      createAutoKeyQuote(jobId, {
        line_items: items
          .filter(i => i.description.trim())
          .map(i => ({
            description: i.description.trim(),
            quantity: Math.max(1, parseFloat(i.quantity || '1')),
            unit_price_cents: dollarsToCents(i.unitPrice),
          })),
        tax_cents: dollarsToCents(tax),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-quotes', jobId] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create quote.')),
  })

  return (
    <Modal title="Create Mobile Services Quote" onClose={onClose}>
      <div className="space-y-4">
        {/* One-tap preset bundles */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>
            Quick add — tap a service
          </p>
          <div className="flex flex-wrap gap-1.5">
            {QUOTE_PRESETS.map(p => (
              <button
                key={p.label}
                type="button"
                onClick={() => addPreset(p)}
                className="text-xs px-2.5 py-1 rounded-full border transition-colors touch-manipulation"
                style={{ borderColor: 'var(--ms-accent)', color: 'var(--ms-accent)', backgroundColor: 'var(--ms-accent-light)' }}
              >
                {p.label} · ${p.price}
              </button>
            ))}
          </div>
        </div>

        {/* Line items */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Line items</p>
          {items.map((item, i) => (
            <div key={i} className="flex gap-2 items-end">
              <div className="flex-1 min-w-0">
                <Input
                  label={i === 0 ? 'Description' : undefined}
                  placeholder="Description"
                  value={item.description}
                  onChange={e => updateItem(i, 'description', e.target.value)}
                />
              </div>
              <div style={{ width: 52 }}>
                <Input
                  label={i === 0 ? 'Qty' : undefined}
                  type="number" min="0.01" step="0.01"
                  value={item.quantity}
                  onChange={e => updateItem(i, 'quantity', e.target.value)}
                />
              </div>
              <div style={{ width: 90 }}>
                <Input
                  label={i === 0 ? 'Price ($)' : undefined}
                  type="number" min="0" step="0.01"
                  placeholder="0.00"
                  value={item.unitPrice}
                  onChange={e => updateItem(i, 'unitPrice', e.target.value)}
                />
              </div>
              {items.length > 1 && (
                <button type="button" onClick={() => removeItem(i)} className="pb-1 text-lg leading-none" style={{ color: 'var(--ms-text-muted)' }} aria-label="Remove">×</button>
              )}
            </div>
          ))}
          <button type="button" onClick={addBlankItem} className="text-xs font-medium" style={{ color: 'var(--ms-accent)' }}>
            + Add line item
          </button>
        </div>

        {/* GST + total */}
        <div className="flex items-center gap-4">
          <div style={{ width: 100 }}>
            <Input label="GST ($)" type="number" step="0.01" min="0" value={tax} onChange={e => setTax(e.target.value)} />
          </div>
          <p className="text-sm font-bold pt-5" style={{ color: 'var(--ms-text)' }}>Total: ${total.toFixed(2)}</p>
        </div>

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button
            className="flex-1"
            onClick={() => quoteMut.mutate()}
            disabled={quoteMut.isPending || items.every(i => !i.description.trim())}
          >
            {quoteMut.isPending ? 'Creating…' : 'Create Quote'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
