import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Phone } from 'lucide-react'
import { createAutoKeyQuickIntake, getApiErrorMessage } from '@/lib/api'
import { Modal, Input, Button } from '@/components/ui'

/**
 * Sends a quick-intake SMS to a customer so they can fill in vehicle details
 * and pick a time, then navigates to the created job. Self-contained modal.
 */
export function SendBookingRequestModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => createAutoKeyQuickIntake({ phone: phone.trim(), full_name: name.trim() || 'Customer' }),
    onSuccess: (res) => {
      navigate(`/auto-key/${res.data.id}`)
      onClose()
    },
    onError: (e: unknown) => setError(getApiErrorMessage(e, 'Could not send booking request.')),
  })

  return (
    <Modal title="Send booking request" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Enter the customer's mobile number. They'll receive an SMS with a link to fill in their vehicle details and preferred date &amp; time.
        </p>
        <Input
          label="Mobile number *"
          type="tel"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          placeholder="e.g. 0412 345 678"
          autoFocus
        />
        <Input
          label="Customer name (optional)"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. Sam Taylor"
        />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
          <Button
            type="button"
            disabled={mut.isPending || !phone.trim()}
            onClick={() => { setError(''); mut.mutate() }}
          >
            <Phone size={16} />
            {mut.isPending ? 'Sending…' : 'Send SMS'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
