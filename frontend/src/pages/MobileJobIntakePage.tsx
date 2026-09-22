import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Camera, Clock, Wrench } from 'lucide-react'
import {
  getApiErrorMessage,
  getPublicAutoKeyIntake,
  submitPublicAutoKeyIntake,
  type PublicAutoKeyIntake,
} from '@/lib/api'
import { preparePhotoFile } from '@/lib/photoUpload'
import { Button, Card, Input, Select, Textarea } from '@/components/ui'

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(reader.error ?? new Error('Could not read photo'))
    reader.readAsDataURL(file)
  })
}

export default function MobileJobIntakePage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()
  const [fullName, setFullName] = useState('')
  const [vehicleMake, setVehicleMake] = useState('')
  const [vehicleModel, setVehicleModel] = useState('')
  const [vehicleYear, setVehicleYear] = useState('')
  const [registrationPlate, setRegistrationPlate] = useState('')
  const [jobAddress, setJobAddress] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [description, setDescription] = useState('')
  const [keyQuantity, setKeyQuantity] = useState('1')
  const [keyType, setKeyType] = useState('')
  const [keyPhotos, setKeyPhotos] = useState<File[]>([])
  const [photoBusy, setPhotoBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const extraInputRef = useRef<HTMLInputElement>(null)

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
  }, [data])

  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  useEffect(() => {
    const urls = keyPhotos.map(file => URL.createObjectURL(file))
    setPreviewUrls(urls)
    return () => urls.forEach(url => URL.revokeObjectURL(url))
  }, [keyPhotos])

  const addKeyPhotos = async (list: FileList | null, replaceFirst = false) => {
    if (!list?.length) return
    setPhotoBusy(true)
    try {
      const incoming = Array.from(list)
      const prepared: File[] = []
      for (const file of incoming) {
        try {
          prepared.push(await preparePhotoFile(file))
        } catch {
          prepared.push(file)
        }
      }
      setKeyPhotos(prev => {
        const base = replaceFirst ? [] : prev
        return [...base, ...prepared].slice(0, 2)
      })
    } finally {
      setPhotoBusy(false)
    }
  }

  const submitMut = useMutation({
    mutationFn: async () => {
      let keyPhotoData: string | undefined
      let extraKeyPhotoData: string | undefined
      if (keyPhotos[0]) {
        try {
          keyPhotoData = await fileToBase64(keyPhotos[0])
          if (keyPhotos[1]) extraKeyPhotoData = await fileToBase64(keyPhotos[1])
        } catch {
          // Photo is requested, not required — still send the rest of the form.
        }
      }
      return submitPublicAutoKeyIntake(token!, {
        full_name: fullName.trim() || undefined,
        vehicle_make: vehicleMake.trim() || undefined,
        vehicle_model: vehicleModel.trim() || undefined,
        vehicle_year: vehicleYear.trim() ? Number(vehicleYear) : undefined,
        registration_plate: registrationPlate.trim() || undefined,
        job_address: jobAddress.trim() || undefined,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
        description: description.trim() || undefined,
        key_quantity: Math.max(1, Number(keyQuantity || '1')),
        key_type: keyType || undefined,
        key_photo_data: keyPhotoData,
        extra_key_photo_data: extraKeyPhotoData,
      }).then(r => r.data)
    },
    onSuccess: () => {
      qc.removeQueries({ queryKey: ['public-auto-key-intake', token] })
    },
    onError: (e: unknown) => setFormError(getApiErrorMessage(e, 'Could not submit.')),
  })

  if (submitMut.isSuccess) {
    return (
      <div className="min-h-screen py-8 px-4 flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <Card className="max-w-md p-8 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-2" style={{ backgroundColor: '#E8F6EE' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1F6D4C" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <p className="text-xl font-semibold" style={{ color: 'var(--ms-text)' }}>
            {submitMut.data?.message ?? 'Request received!'}
          </p>
          <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
            We'll be in touch shortly to confirm your booking. You can close this page.
          </p>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="text-center" style={{ color: 'var(--ms-text-muted)' }}>
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
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>
            Link unavailable
          </h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>{msg}</p>
        </div>
      </div>
    )
  }

  const info = data as PublicAutoKeyIntake

  return (
    <div className="min-h-screen py-6 px-4 sm:py-10 sm:px-5" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Wrench size={22} style={{ color: 'var(--ms-accent-hover)' }} />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--ms-text)' }}>
            Complete your job details
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            {info.shop_name} · Job #{info.job_number}
          </p>
        </div>

        <Card className="p-4 sm:p-5 space-y-3">
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
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
          <Input label="Where should we meet? (address)" value={jobAddress} onChange={e => setJobAddress(e.target.value)} placeholder="For mobile jobs" />
          <Input label="Preferred date & time (optional)" type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input label="Number of keys" type="number" min={1} value={keyQuantity} onChange={e => setKeyQuantity(e.target.value)} />
            <Select label="Key type" value={keyType} onChange={e => setKeyType(e.target.value)}>
              <option value="">Not sure</option>
              <option value="Bladed">Bladed (turns key to start car)</option>
              <option value="Proximity">Proximity (push button to start car)</option>
            </Select>
          </div>
          <div className="space-y-2 pt-1">
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
              Photo of the car key
            </p>
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              Please photograph the key if you can — it helps us bring the right blanks. Optional if you can&apos;t take one now.
            </p>
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={e => {
                void addKeyPhotos(e.target.files, true)
                e.target.value = ''
              }}
            />
            <input
              ref={extraInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={e => {
                void addKeyPhotos(e.target.files)
                e.target.value = ''
              }}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={photoBusy}
                onClick={() => cameraInputRef.current?.click()}
              >
                <Camera size={16} />
                {photoBusy ? 'Processing…' : keyPhotos.length ? 'Retake photo' : 'Take photo of the key'}
              </Button>
              {keyPhotos.length === 1 && (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={photoBusy}
                  onClick={() => extraInputRef.current?.click()}
                >
                  Add another (optional)
                </Button>
              )}
            </div>
            {previewUrls.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {previewUrls.map((url, i) => (
                  <div key={url} className="relative">
                    <img
                      src={url}
                      alt={i === 0 ? 'Car key photo' : `Extra key photo ${i + 1}`}
                      className="w-20 h-20 object-cover rounded-lg"
                      style={{ border: '1px solid var(--ms-border)' }}
                    />
                    <button
                      type="button"
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full text-xs leading-none"
                      style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
                      aria-label="Remove photo"
                      onClick={() => setKeyPhotos(prev => prev.filter((_, j) => j !== i))}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <Textarea label="Anything else we should know?" value={description} onChange={e => setDescription(e.target.value)} rows={3} />

          {formError ? <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{formError}</p> : null}

          <Button
            className="w-full"
            type="button"
            disabled={submitMut.isPending || photoBusy}
            onClick={() => {
              setFormError('')
              if (!vehicleMake.trim() && !description.trim()) {
                setFormError('Please enter the vehicle make or describe what you need.')
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
