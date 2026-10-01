/**
 * Public car key enquiry form. No auth: the ingest id in the URL identifies the network.
 * Submits to POST /v1/public/key-enquiry/:ingestId, which routes into the operator Lead Inbox.
 * Built mobile-first with big tap targets so it works from a phone beside a locked car.
 */
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { submitKeyEnquiry, getApiErrorMessage } from '@/lib/api'

const SERVICES = [
  { value: 'lost_all_keys', label: 'Lost all keys' },
  { value: 'spare_key', label: 'Spare key' },
  { value: 'broken_key', label: 'Broken / damaged key' },
  { value: 'locked_out', label: 'Locked out' },
  { value: 'remote_repair', label: 'Remote / fob repair' },
  { value: 'other', label: 'Something else' },
]
const KEY_TYPES = [
  { value: 'standard', label: 'Standard metal key' },
  { value: 'remote_flip', label: 'Remote / flip key' },
  { value: 'push_start', label: 'Push-button start' },
  { value: 'unsure', label: 'Not sure' },
]
const LOCATIONS = [
  { value: 'home', label: 'Home' },
  { value: 'work', label: 'Work' },
  { value: 'roadside', label: 'Roadside' },
  { value: 'carpark', label: 'Car park' },
  { value: 'other', label: 'Other' },
]
const URGENCY = [
  { value: 'asap', label: 'ASAP' },
  { value: 'today', label: 'Today' },
  { value: 'this_week', label: 'This week' },
  { value: 'flexible', label: 'Flexible' },
]
const STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']

const inputClass = 'w-full px-3 py-3 rounded-lg text-base outline-none border focus:border-[#2B3990]'
const inputStyle = { border: '1px solid #C4C4C4', color: '#1A1A1A', backgroundColor: '#fff' }

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium" style={{ color: '#1A1A1A' }}>
        {label}{required && <span style={{ color: '#E31837' }}> *</span>}
      </label>
      {children}
      {hint && <p className="text-xs" style={{ color: '#787878' }}>{hint}</p>}
    </div>
  )
}

function Chips({ options, value, onChange }: { options: { value: string; label: string }[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup">
      {options.map(o => {
        const on = value === o.value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(on ? '' : o.value)}
            className="px-4 py-2.5 rounded-full text-sm font-medium border transition"
            style={on ? { backgroundColor: '#2B3990', color: '#fff', borderColor: '#2B3990' } : { backgroundColor: '#fff', color: '#1A1A1A', borderColor: '#C4C4C4' }}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export default function KeyEnquiryPage() {
  const { ingestId = '' } = useParams()
  const [f, setF] = useState({
    service: '', key_type: '', has_working_key: '', location_type: '', urgency: '',
    vehicle_make: '', vehicle_model: '', vehicle_year: '', registration_plate: '',
    suburb: '', state_code: 'NSW', street_address: '',
    customer_name: '', phone: '', email: '', notes: '', website: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const text = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF(s => ({ ...s, [k]: e.target.value }))
  const pick = (k: keyof typeof f) => (v: string) => setF(s => ({ ...s, [k]: v }))

  const ready = f.service && f.vehicle_make.trim() && f.suburb.trim() && f.customer_name.trim() && f.phone.trim().length >= 6

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ready) return
    setError('')
    setSubmitting(true)
    const opt = (v: string) => v.trim() || undefined
    try {
      await submitKeyEnquiry(ingestId, {
        customer_name: f.customer_name.trim(),
        phone: f.phone.trim(),
        email: opt(f.email),
        suburb: f.suburb.trim(),
        state_code: f.state_code,
        street_address: opt(f.street_address),
        location_type: opt(f.location_type),
        service: f.service,
        key_type: opt(f.key_type),
        vehicle_make: f.vehicle_make.trim(),
        vehicle_model: opt(f.vehicle_model),
        vehicle_year: opt(f.vehicle_year),
        registration_plate: opt(f.registration_plate),
        has_working_key: f.has_working_key === '' ? undefined : f.has_working_key === 'yes',
        urgency: opt(f.urgency),
        notes: opt(f.notes),
        website: f.website || undefined,
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
        <div className="max-w-md w-full text-center space-y-3 p-8 rounded-2xl shadow-sm" style={{ backgroundColor: '#fff' }}>
          <div className="text-4xl">✓</div>
          <h1 className="text-xl font-bold" style={{ color: '#1A1A1A' }}>Enquiry received</h1>
          <p className="text-sm" style={{ color: '#484848' }}>
            A mobile key technician near you will contact you shortly with a quote.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 sm:p-8" style={{ backgroundColor: '#F4F4F4' }}>
      <div className="max-w-lg mx-auto">
        <h1 className="text-2xl font-bold" style={{ color: '#1A1A1A' }}>Car key enquiry</h1>
        <p className="text-sm mt-1 mb-5" style={{ color: '#787878' }}>
          Tell us what happened and we'll send you a quote from a mobile technician near you. Takes about a minute.
        </p>

        <form onSubmit={submit} className="space-y-6 p-5 sm:p-6 rounded-2xl shadow-sm" style={{ backgroundColor: '#fff' }}>
          <Field label="What do you need?" required>
            <Chips options={SERVICES} value={f.service} onChange={pick('service')} />
          </Field>

          <Field label="Key type">
            <Chips options={KEY_TYPES} value={f.key_type} onChange={pick('key_type')} />
          </Field>

          <Field label="Do you still have a working key?">
            <Chips options={[{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }]} value={f.has_working_key} onChange={pick('has_working_key')} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Car make" required>
              <input className={inputClass} style={inputStyle} value={f.vehicle_make} onChange={text('vehicle_make')} placeholder="Toyota" autoComplete="off" />
            </Field>
            <Field label="Model">
              <input className={inputClass} style={inputStyle} value={f.vehicle_model} onChange={text('vehicle_model')} placeholder="Camry" autoComplete="off" />
            </Field>
            <Field label="Year">
              <input className={inputClass} style={inputStyle} value={f.vehicle_year} onChange={text('vehicle_year')} placeholder="2019" inputMode="numeric" maxLength={4} />
            </Field>
            <Field label="Rego">
              <input className={inputClass} style={inputStyle} value={f.registration_plate} onChange={text('registration_plate')} placeholder="ABC123" autoCapitalize="characters" />
            </Field>
          </div>

          <Field label="Where is the car?">
            <Chips options={LOCATIONS} value={f.location_type} onChange={pick('location_type')} />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Field label="Suburb" required>
                <input className={inputClass} style={inputStyle} value={f.suburb} onChange={text('suburb')} placeholder="Parramatta" autoComplete="address-level2" />
              </Field>
            </div>
            <Field label="State" required>
              <select className={inputClass} style={inputStyle} value={f.state_code} onChange={text('state_code')}>
                {STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Street address" hint="Optional, helps the technician find you faster.">
            <input className={inputClass} style={inputStyle} value={f.street_address} onChange={text('street_address')} autoComplete="street-address" />
          </Field>

          <Field label="When do you need it?">
            <Chips options={URGENCY} value={f.urgency} onChange={pick('urgency')} />
          </Field>

          <Field label="Anything else we should know?">
            <textarea className={inputClass} style={inputStyle} rows={3} value={f.notes} onChange={text('notes')} placeholder="e.g. keys are in the car, basement car park, immobiliser light flashing" />
          </Field>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Your name" required>
              <input className={inputClass} style={inputStyle} value={f.customer_name} onChange={text('customer_name')} autoComplete="name" />
            </Field>
            <Field label="Mobile number" required>
              <input className={inputClass} style={inputStyle} value={f.phone} onChange={text('phone')} type="tel" autoComplete="tel" placeholder="04XX XXX XXX" />
            </Field>
          </div>
          <Field label="Email" hint="Optional.">
            <input className={inputClass} style={inputStyle} value={f.email} onChange={text('email')} type="email" autoComplete="email" />
          </Field>

          {/* Honeypot: hidden from people, bots tend to fill it. */}
          <div aria-hidden="true" style={{ position: 'absolute', left: '-9999px' }}>
            <input tabIndex={-1} autoComplete="off" value={f.website} onChange={text('website')} name="website" />
          </div>

          {error && <p className="text-sm" style={{ color: '#E31837' }}>{error}</p>}

          <button
            type="submit"
            disabled={submitting || !ready}
            className="w-full py-3.5 rounded-lg text-base font-semibold transition disabled:opacity-50"
            style={{ backgroundColor: '#2B3990', color: '#fff' }}
          >
            {submitting ? 'Sending…' : 'Get a quote'}
          </button>
        </form>
      </div>
    </div>
  )
}
