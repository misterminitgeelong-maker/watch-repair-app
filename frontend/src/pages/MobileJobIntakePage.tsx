import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Clock, Minus, Wrench } from 'lucide-react'
import {
  getApiErrorMessage,
  getPublicAutoKeyIntake,
  submitPublicAutoKeyIntake,
  type PublicAutoKeyIntake,
} from '@/lib/api'
import { AUTO_KEY_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { Button, Card, Input, Select, Textarea } from '@/components/ui'

export default function MobileJobIntakePage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()
  const [extraLines, setExtraLines] = useState<Array<{ preset: string; custom: string }>>([])
  const [fullName, setFullName] = useState('')
  const [vehicleMake, setVehicleMake] = useState('')
  const [vehicleModel, setVehicleModel] = useState('')
  const [vehicleYear, setVehicleYear] = useState('')
  const [registrationPlate, setRegistrationPlate] = useState('')
  const [vin, setVin] = useState('')
  const [jobAddress, setJobAddress] = useState('')
  const [jobType, setJobType] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [description, setDescription] = useState('')
  const [keyQuantity, setKeyQuantity] = useState('1')
  const [keyType, setKeyType] = useState('')
  const [bladeCode, setBladeCode] = useState('')
  const [chipType, setChipType] = useState('')
  const [techNotes, setTechNotes] = useState('')
  const [formError, setFormError] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-intake', token],
    queryFn: () => getPublicAutoKeyIntake(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  useEffect(() => {
    if (!data) return
    const d = data as PublicAutoKeyIntake
    setVehicleMake(d.vehicle_make ?? '')
    setVehicleModel(d.vehicle_model ?? '')
    setVehicleYear(d.vehicle_year != null ? String(d.vehicle_year) : '')
    setRegistrationPlate(d.registration_plate ?? '')
    setJobAddress(d.job_address ?? '')
    setJobType(d.job_type ?? '')
  }, [data])

  const submitMut = useMutation({
    mutationFn: () => {
      const additional_services = extraLines
        .map(r => ({
          preset: r.preset.trim() || undefined,
          custom: r.custom.trim() || undefined,
        }))
        .filter(r => r.preset || r.custom)
      return submitPublicAutoKeyIntake(token!, {
        full_name: fullName.trim() || undefined,
        vehicle_make: vehicleMake.trim() || undefined,
        vehicle_model: vehicleModel.trim() || undefined,
        vehicle_year: vehicleYear.trim() ? Number(vehicleYear) : undefined,
        registration_plate: registrationPlate.trim() || undefined,
        vin: vin.trim() || undefined,
        job_address: jobAddress.trim() || undefined,
        job_type: jobType || undefined,
        additional_services: additional_services.length ? additional_services : undefined,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
        description: description.trim() || undefined,
        key_quantity: Math.max(1, Number(keyQuantity || '1')),
        key_type: keyType.trim() || undefined,
        blade_code: bladeCode.trim() || undefined,
        chip_type: chipType.trim() || undefined,
        tech_notes: techNotes.trim() || undefined,
      }).then(r => r.data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-auto-key-intake', token] })
    },
    onError: (e: unknown) => setFormError(getApiErrorMessage(e, 'Could not submit.')),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    const msg =
      axios.isAxiosError(error) && error.response?.status === 404
        ? 'This link is not valid or the job has already been completed. Contact the shop if you need help.'
        : getApiErrorMessage(error, 'Could not load form.')
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Link unavailable
          </h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>{msg}</p>
        </div>
      </div>
    )
  }

  const info = data as PublicAutoKeyIntake

  if (submitMut.isSuccess) {
    return (
      <div className="min-h-screen py-8 px-4 flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <Card className="max-w-md p-8 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-2" style={{ backgroundColor: '#E8F6EE' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1F6D4C" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <p className="text-xl font-semibold" style={{ color: 'var(--cafe-text)', fontFamily: "'Playfair Display', Georgia, serif" }}>
            {submitMut.data?.message ?? 'Request received!'}
          </p>
          <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            We'll be in touch shortly to confirm your booking. You can close this page.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-6 px-4 sm:py-10 sm:px-5" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Wrench size={22} style={{ color: 'var(--cafe-gold-dark)' }} />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Complete your job details
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
            {info.shop_name} · Job #{info.job_number}
          </p>
        </div>

        <Card className="p-4 sm:p-5 space-y-3">
          <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
            Hi{info.customer_first_name_hint ? ` ${info.customer_first_name_hint}` : ''} — please confirm your details so we can schedule and quote accurately.
          </p>
          <Input
            label="Your name (if different)"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
            placeholder="Optional"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Vehicle make" value={vehicleMake} onChange={e => setVehicleMake(e.target.value)} placeholder="e.g. Toyota" />
            <Input label="Vehicle model" value={vehicleModel} onChange={e => setVehicleModel(e.target.value)} placeholder="e.g. Hilux" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Year" type="number" value={vehicleYear} onChange={e => setVehicleYear(e.target.value)} placeholder="e.g. 2020" />
            <Input label="Registration" value={registrationPlate} onChange={e => setRegistrationPlate(e.target.value)} placeholder="Optional" />
          </div>
          <Input label="VIN" value={vin} onChange={e => setVin(e.target.value)} placeholder="Optional" />
          <Input label="Where should we meet? (address)" value={jobAddress} onChange={e => setJobAddress(e.target.value)} placeholder="For mobile jobs" />
          <Select label="What do you need? *" value={jobType} onChange={e => setJobType(e.target.value)}>
            <option value="">Choose…</option>
            {AUTO_KEY_JOB_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </Select>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>More work on the same visit (optional)</p>
            {extraLines.map((row, idx) => (
              <div key={idx} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2 items-end">
                <Select
                  label={idx === 0 ? 'Type' : ''}
                  value={row.preset}
                  onChange={e => setExtraLines(xs => xs.map((r, i) => (i === idx ? { ...r, preset: e.target.value } : r)))}
                >
                  <option value="">—</option>
                  {AUTO_KEY_JOB_TYPES.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </Select>
                <Input
                  label={idx === 0 ? 'Custom' : ''}
                  value={row.custom}
                  onChange={e => setExtraLines(xs => xs.map((r, i) => (i === idx ? { ...r, custom: e.target.value } : r)))}
                  placeholder="Describe…"
                />
                <Button type="button" variant="ghost" className="shrink-0" aria-label="Remove" onClick={() => setExtraLines(xs => xs.filter((_, i) => i !== idx))}>
                  <Minus size={18} />
                </Button>
              </div>
            ))}
            <Button type="button" variant="secondary" onClick={() => setExtraLines(xs => [...xs, { preset: '', custom: '' }])}>
              Add another line
            </Button>
          </div>

          <Input label="Preferred date & time (optional)" type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} />
          <Textarea label="Anything else we should know?" value={description} onChange={e => setDescription(e.target.value)} rows={3} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Number of keys" type="number" min={1} value={keyQuantity} onChange={e => setKeyQuantity(e.target.value)} />
            <Input label="Key type (if known)" value={keyType} onChange={e => setKeyType(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Blade / blank ref." value={bladeCode} onChange={e => setBladeCode(e.target.value)} />
            <Input label="Chip type" value={chipType} onChange={e => setChipType(e.target.value)} />
          </div>
          <Textarea label="Your notes for the technician" value={techNotes} onChange={e => setTechNotes(e.target.value)} rows={2} />

          {formError ? <p className="text-sm" style={{ color: '#C96A5A' }}>{formError}</p> : null}

          <Button
            className="w-full"
            type="button"
            disabled={submitMut.isPending}
            onClick={() => {
              setFormError('')
              if (!jobType.trim() && !vehicleMake.trim() && !description.trim()) {
                setFormError('Please choose a service type, enter the vehicle make, or describe what you need.')
                return
              }
              submitMut.mutate()
            }}
          >
            {submitMut.isPending ? 'Sending…' : 'Submit details'}
          </Button>
        </Card>
      </div>
    </div>
  )
}
