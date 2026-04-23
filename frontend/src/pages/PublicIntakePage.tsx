/**
 * Public intake form — embedded on the Mister Minit website.
 * No auth required. Submits to POST /v1/public/intake.
 * Styled to be minimal and embeddable.
 */
import { useState } from 'react'
import { submitPublicIntake, getApiErrorMessage } from '@/lib/api'

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium" style={{ color: '#1A1A1A' }}>
        {label}{required && <span style={{ color: '#E31837' }}> *</span>}
      </label>
      {children}
    </div>
  )
}

const inputClass = 'w-full px-3 py-2.5 rounded-lg text-sm outline-none border transition focus:border-[#2B3990]'
const inputStyle = { border: '1px solid #C4C4C4', color: '#1A1A1A', backgroundColor: '#fff' }

export default function PublicIntakePage() {
  const [form, setForm] = useState({
    customer_name: '',
    customer_phone: '',
    customer_email: '',
    job_address: '',
    vehicle_make: '',
    vehicle_model: '',
    vehicle_year: '',
    registration_plate: '',
    description: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await submitPublicIntake({
        customer_name: form.customer_name.trim(),
        customer_phone: form.customer_phone.trim() || undefined,
        customer_email: form.customer_email.trim() || undefined,
        job_address: form.job_address.trim(),
        vehicle_make: form.vehicle_make.trim() || undefined,
        vehicle_model: form.vehicle_model.trim() || undefined,
        vehicle_year: form.vehicle_year.trim() || undefined,
        registration_plate: form.registration_plate.trim() || undefined,
        description: form.description.trim() || undefined,
      })
      setDone(true)
    } catch (err) {
      setError(getApiErrorMessage(err) || 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ backgroundColor: '#F4F4F4' }}>
        <div className="max-w-md w-full text-center space-y-4 p-8 rounded-2xl shadow-sm" style={{ backgroundColor: '#fff' }}>
          <div className="text-4xl">✓</div>
          <h1 className="text-xl font-bold" style={{ color: '#1A1A1A' }}>Request received!</h1>
          <p className="text-sm" style={{ color: '#484848' }}>
            A Mister Minit technician in your area will be in touch shortly to confirm your booking.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: '#F4F4F4' }}>
      <div className="max-w-lg mx-auto">
        <div className="mb-6">
          <img src="/minit-logo.jpg" alt="Mister Minit" className="h-10 object-contain mb-4" />
          <h1 className="text-2xl font-bold" style={{ color: '#1A1A1A' }}>Request a mobile key service</h1>
          <p className="text-sm mt-1" style={{ color: '#787878' }}>
            Fill in your details and we'll send the nearest technician to you.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-6 rounded-2xl shadow-sm" style={{ backgroundColor: '#fff' }}>
          <Field label="Your name" required>
            <input
              className={inputClass}
              style={inputStyle}
              value={form.customer_name}
              onChange={set('customer_name')}
              placeholder="Jane Smith"
              required
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Phone">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.customer_phone}
                onChange={set('customer_phone')}
                placeholder="+61 4XX XXX XXX"
                type="tel"
              />
            </Field>
            <Field label="Email">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.customer_email}
                onChange={set('customer_email')}
                placeholder="jane@example.com"
                type="email"
              />
            </Field>
          </div>

          <Field label="Job address" required>
            <input
              className={inputClass}
              style={inputStyle}
              value={form.job_address}
              onChange={set('job_address')}
              placeholder="123 Main St, Sydney NSW 2000"
              required
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Vehicle make">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.vehicle_make}
                onChange={set('vehicle_make')}
                placeholder="Toyota"
              />
            </Field>
            <Field label="Vehicle model">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.vehicle_model}
                onChange={set('vehicle_model')}
                placeholder="Camry"
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Year">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.vehicle_year}
                onChange={set('vehicle_year')}
                placeholder="2019"
                maxLength={4}
              />
            </Field>
            <Field label="Registration plate">
              <input
                className={inputClass}
                style={inputStyle}
                value={form.registration_plate}
                onChange={set('registration_plate')}
                placeholder="ABC123"
              />
            </Field>
          </div>

          <Field label="Additional details">
            <textarea
              className={inputClass}
              style={inputStyle}
              value={form.description}
              onChange={set('description')}
              placeholder="Describe the issue or any special requirements…"
              rows={3}
            />
          </Field>

          {error && <p className="text-sm" style={{ color: '#E31837' }}>{error}</p>}

          <button
            type="submit"
            disabled={submitting || !form.customer_name.trim() || !form.job_address.trim()}
            className="w-full py-3 rounded-lg text-sm font-semibold transition disabled:opacity-50"
            style={{ backgroundColor: '#2B3990', color: '#fff' }}
          >
            {submitting ? 'Submitting…' : 'Request technician'}
          </button>
        </form>
      </div>
    </div>
  )
}
