import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Clock, Minus, Plus, Ticket, X } from 'lucide-react'
import MedalPreview from '@/components/engraving/MedalPreview'
import {
  createPublicEngravingBatch,
  ENGRAVING_BATCH_MAX,
  getPublicEngravingEvent,
  type EngravingPlace,
} from '@/lib/api/engraving'
import { getApiErrorMessage } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const PLACE_LABELS: Record<EngravingPlace, string> = {
  '1st': '1st',
  '2nd': '2nd',
  '3rd': '3rd',
  Participant: 'Participant',
  None: 'No place',
}

const fieldStyle: React.CSSProperties = {
  height: 48,
  padding: '0 14px',
  fontSize: 16,
  borderRadius: 'var(--ms-radius)',
  border: '1px solid var(--ms-border-strong, var(--ms-border))',
  background: 'var(--ms-surface)',
  color: 'var(--ms-text)',
  width: '100%',
  boxSizing: 'border-box',
}

function Centered({ title, body }: { title: string; body: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>{title}</h1>
        <p style={{ color: 'var(--ms-text-muted)' }}>{body}</p>
      </div>
    </div>
  )
}

interface MedalDraft {
  key: number
  name: string
  line2: string
  place: EngravingPlace
  qty: number
}

let nextKey = 1
const blankMedal = (): MedalDraft => ({ key: nextKey++, name: '', line2: '', place: '1st', qty: 1 })

export default function PublicEngravingOrderPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [medals, setMedals] = useState<MedalDraft[]>(() => [blankMedal()])
  const [ticket, setTicket] = useState('')
  const [phone, setPhone] = useState('')
  const [checked, setChecked] = useState(false)

  const { data: event, isLoading, isError } = useQuery({
    queryKey: ['public-engraving-event', token],
    queryFn: () => getPublicEngravingEvent(token!).then((r) => r.data),
    enabled: !!token,
    retry: false,
    refetchInterval: 30000,
  })

  const submit = useMutation({
    mutationFn: () =>
      createPublicEngravingBatch(token!, {
        ticket_number: ticket.trim(),
        phone: phone.trim() || null,
        orders: medals.map((m) => ({
          athlete_name: m.name.trim(),
          line2: m.line2.trim() || null,
          place: m.place,
          qty: m.qty,
        })),
      }).then((r) => r.data),
    onSuccess: (orders) => navigate(`/engrave/o/${orders[0].status_token}`, { replace: true }),
  })

  const update = (key: number, patch: Partial<MedalDraft>) =>
    setMedals((list) => list.map((m) => (m.key === key ? { ...m, ...patch } : m)))

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-muted)' }}>
        <Clock className="animate-spin" size={28} aria-label="Loading" />
      </div>
    )
  }
  if (isError || !event) {
    return <Centered title="Stall not found" body="This engraving link isn't working. Please order at the stall." />
  }

  const totalMedals = medals.reduce((sum, m) => sum + m.qty, 0)
  const total = formatCents(event.price_cents * totalMedals)
  const allNamed = medals.every((m) => m.name.trim().length > 0)
  const canSubmit = event.accepting_orders && allNamed && ticket.trim().length > 0 && checked && !submit.isPending

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (canSubmit) submit.mutate()
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}>
      <header className="px-5 py-4 flex items-center justify-between gap-3" style={{ background: 'var(--ms-ink, #0A0A0A)', color: '#fff', borderBottom: '2px solid #C99A3B' }}>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] leading-tight">Medal engraving</p>
          <p className="text-xs opacity-80 truncate">{[event.shop_name, event.name].filter(Boolean).join(' · ')}</p>
        </div>
        {event.accepting_orders && (
          <span className="shrink-0 rounded-[var(--ms-radius)] px-3 py-1.5 text-xs font-semibold" style={{ background: 'rgba(255,255,255,0.14)' }}>
            Wait ~{Math.max(5, event.wait_minutes)} min
          </span>
        )}
      </header>

      <main className="mx-auto max-w-md px-5 py-6 flex flex-col gap-5">
        <div>
          <h1 className="text-4xl leading-none" style={{ fontFamily: 'var(--ms-font-display)', fontWeight: 400 }}>Engrave your medals</h1>
          <p className="mt-2 text-[15px]" style={{ color: 'var(--ms-text-mid)' }}>
            Grab a ticket from the pile, fill this in and pay at the stall. Put the other half of the ticket in the tub with your medals. {formatCents(event.price_cents)} per medal.
          </p>
        </div>

        {!event.accepting_orders && (
          <div className="rounded-[var(--ms-radius)] px-4 py-3 text-sm font-medium" style={{ background: 'var(--ms-badge-orange-bg)', color: 'var(--ms-badge-orange-text)' }}>
            {event.status === 'closed' ? 'Engraving has finished for this event.' : 'Orders are paused for a moment. Please try again shortly or ask at the stall.'}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5 rounded-[var(--ms-radius)] p-4" style={{ background: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <label htmlFor="engr-ticket" className="text-sm font-semibold inline-flex items-center gap-2"><Ticket size={16} aria-hidden />Ticket number</label>
            <input id="engr-ticket" value={ticket} onChange={(e) => setTicket(e.target.value)} maxLength={12} autoComplete="off" inputMode="text" placeholder="The number printed on your ticket" style={fieldStyle} required />
            <span className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>Keep one half of the ticket. The other half goes in the tub with your medals.</span>
          </div>

          {medals.map((m, i) => {
            const id = `engr-${m.key}`
            return (
              <fieldset key={m.key} className="flex flex-col gap-4 rounded-[var(--ms-radius)] p-4 min-w-0" style={{ background: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
                <legend className="sr-only">Medal {i + 1}</legend>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold uppercase tracking-[0.12em]" style={{ color: 'var(--ms-text-mid)' }}>Medal {i + 1}</p>
                  {medals.length > 1 && (
                    <button type="button" aria-label={`Remove medal ${i + 1}`} onClick={() => setMedals((list) => list.filter((x) => x.key !== m.key))} className="h-9 w-9 flex items-center justify-center rounded-full" style={{ color: 'var(--ms-text-mid)' }}>
                      <X size={18} />
                    </button>
                  )}
                </div>
                <div className="flex flex-col items-center gap-2">
                  <MedalPreview name={m.name} line2={m.line2} place={m.place} />
                  <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>Live preview, engraved exactly as shown</p>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor={`${id}-name`} className="text-sm font-semibold">Athlete's name</label>
                  <input id={`${id}-name`} value={m.name} onChange={(e) => update(m.key, { name: e.target.value })} maxLength={event.name_max} autoComplete="off" placeholder="e.g. Mia Thompson" style={fieldStyle} required />
                  <span className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>Up to {event.name_max} characters. Long names shrink to fit.</span>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor={`${id}-line2`} className="text-sm font-semibold">Event or second line <span className="font-normal" style={{ color: 'var(--ms-text-mid)' }}>(optional)</span></label>
                  <input id={`${id}-line2`} value={m.line2} onChange={(e) => update(m.key, { line2: e.target.value })} maxLength={event.line2_max} autoComplete="off" placeholder="e.g. U9 Girls 100m" style={fieldStyle} />
                </div>

                <div className="flex flex-col gap-2" role="group" aria-label={`Place for medal ${i + 1}`}>
                  <span className="text-sm font-semibold">Place</span>
                  <div className="grid grid-cols-3 gap-2">
                    {event.places.map((p) => {
                      const active = p === m.place
                      return (
                        <button
                          key={p}
                          type="button"
                          aria-pressed={active}
                          onClick={() => update(m.key, { place: p })}
                          className="h-11 rounded-[var(--ms-radius)] text-sm font-semibold"
                          style={{
                            border: `1px solid ${active ? 'var(--ms-text)' : 'var(--ms-border)'}`,
                            background: active ? 'var(--ms-text)' : 'var(--ms-surface)',
                            color: active ? 'var(--ms-bg)' : 'var(--ms-text)',
                          }}
                        >
                          {PLACE_LABELS[p]}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span id={`${id}-qty`} className="text-sm font-semibold">How many of this medal?</span>
                  <div className="flex items-center gap-1 rounded-[var(--ms-radius)] p-0.5" style={{ border: '1px solid var(--ms-border)', background: 'var(--ms-surface)' }} role="group" aria-labelledby={`${id}-qty`}>
                    <button type="button" aria-label="One fewer medal" onClick={() => update(m.key, { qty: Math.max(1, m.qty - 1) })} className="h-11 w-11 flex items-center justify-center"><Minus size={18} /></button>
                    <span className="min-w-7 text-center text-lg font-bold" aria-live="polite">{m.qty}</span>
                    <button type="button" aria-label="One more medal" onClick={() => update(m.key, { qty: Math.min(20, m.qty + 1) })} className="h-11 w-11 flex items-center justify-center"><Plus size={18} /></button>
                  </div>
                </div>
              </fieldset>
            )
          })}

          {medals.length < ENGRAVING_BATCH_MAX && (
            <button
              type="button"
              onClick={() => setMedals((list) => [...list, blankMedal()])}
              className="h-12 rounded-[var(--ms-radius)] text-sm font-semibold inline-flex items-center justify-center gap-2"
              style={{ border: '1px dashed var(--ms-border-strong, var(--ms-text-mid))', color: 'var(--ms-text)' }}
            >
              <Plus size={16} aria-hidden />Add another medal
            </button>
          )}

          <div className="flex flex-col gap-1.5">
            <label htmlFor="engr-phone" className="text-sm font-semibold">Mobile for your "ready" text <span className="font-normal" style={{ color: 'var(--ms-text-mid)' }}>(optional)</span></label>
            <input id="engr-phone" type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="04xx xxx xxx" style={fieldStyle} />
          </div>

          <label className="flex items-start gap-3 text-sm leading-snug cursor-pointer">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0" style={{ accentColor: 'var(--ms-accent)' }} />
            <span>I've checked the spelling. The medals are engraved exactly as typed.</span>
          </label>

          {submit.isError && (
            <p role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>
              {getApiErrorMessage(submit.error, "Couldn't place your order. Please try again or ask at the stall.")}
            </p>
          )}

          <div className="flex flex-col gap-3 pt-4" style={{ borderTop: '1px solid var(--ms-border)' }}>
            <div className="flex items-baseline justify-between">
              <span className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>{totalMedals} × {formatCents(event.price_cents)}</span>
              <span className="text-2xl font-bold">Total {total}</span>
            </div>
            <button
              type="submit"
              disabled={!canSubmit}
              className="h-14 rounded-[var(--ms-radius)] text-base font-bold disabled:opacity-60"
              style={{ background: canSubmit ? 'var(--ms-accent)' : 'var(--ms-border)', color: canSubmit ? 'var(--ms-on-accent)' : 'var(--ms-text-mid)' }}
            >
              {submit.isPending
                ? 'Placing order…'
                : !ticket.trim()
                  ? 'Enter your ticket number to order'
                  : !checked
                    ? 'Tick the spelling check to order'
                    : `Place order · pay ${total} at the stall`}
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
