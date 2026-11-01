import { Select } from '@/components/ui'

export type CompletionPayment = '' | 'eftpos' | 'cash' | 'bank'

/** Asked when a Mobile Services job is completed: was the customer paid on the spot? */
export function CompletionPaymentPicker({
  value,
  onChange,
  disabled,
}: {
  value: CompletionPayment
  onChange: (next: CompletionPayment) => void
  disabled?: boolean
}) {
  return (
    <div className="mt-3">
      <Select
        label="Payment taken?"
        value={value}
        onChange={e => onChange(e.target.value as CompletionPayment)}
        disabled={disabled}
      >
        <option value="">Not paid yet (send payment link)</option>
        <option value="eftpos">Paid by EFTPOS</option>
        <option value="cash">Paid in cash</option>
        <option value="bank">Paid by bank transfer</option>
      </Select>
      {value && (
        <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          The invoice is marked paid now and no payment link is sent.
        </p>
      )}
    </div>
  )
}
