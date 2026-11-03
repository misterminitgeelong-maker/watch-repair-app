import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { Award, Copy, Plus, Printer, QrCode } from 'lucide-react'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Spinner } from '@/components/ui'
import {
  createEngravingEvent,
  listEngravingEvents,
  type EngravingEvent,
} from '@/lib/api/engraving'
import { getApiErrorMessage } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const STATUS_LABEL: Record<EngravingEvent['status'], string> = {
  open: 'Taking orders',
  paused: 'Paused',
  closed: 'Closed',
}

function formatEventDate(value: string | null): string {
  if (!value) return ''
  const d = new Date(`${value}T00:00:00`)
  return d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}

function NewEventModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [location, setLocation] = useState('')
  const [price, setPrice] = useState('15.00')
  const [minutes, setMinutes] = useState('3')
  const [sms, setSms] = useState(true)
  const [card, setCard] = useState(true)

  const create = useMutation({
    mutationFn: () =>
      createEngravingEvent({
        name: name.trim(),
        event_date: date || null,
        location: location.trim() || null,
        price_cents: Math.round(parseFloat(price || '0') * 100),
        minutes_per_medal: Math.max(1, parseInt(minutes || '3', 10)),
        sms_enabled: sms,
        online_payments: card,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engraving-events'] })
      onClose()
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (name.trim()) create.mutate()
  }

  return (
    <Modal title="New engraving event" onClose={onClose} closeDisabled={create.isPending}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Input label="Event name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Little Athletics — Saturday meet" required autoFocus />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <Input label="Location" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Optional" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Price per medal ($)" type="number" min="0" step="0.50" value={price} onChange={(e) => setPrice(e.target.value)} />
          <Input label="Minutes per medal" type="number" min="1" step="1" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
          <input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} />
          Text parents when their medal is ready
        </label>
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
          <input type="checkbox" checked={card} onChange={(e) => setCard(e.target.checked)} />
          Let parents pay by card online (needs card payments set up in Settings)
        </label>
        {create.isError && <p className="text-sm" role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(create.error, "Couldn't create the event.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={create.isPending}>Cancel</Button>
          <Button type="submit" disabled={!name.trim() || create.isPending}>{create.isPending ? 'Creating…' : 'Create event'}</Button>
        </div>
      </form>
    </Modal>
  )
}

export function EngravingQrModal({ event, onClose }: { event: EngravingEvent; onClose: () => void }) {
  const [qr, setQr] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    QRCode.toDataURL(event.public_url, { width: 600, margin: 1 }).then(setQr).catch(() => setQr(null))
  }, [event.public_url])

  function printSign() {
    if (!qr) return
    const w = window.open('', '_blank', 'width=800,height=1000')
    if (!w) return
    const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)
    w.document.write(`<!doctype html><html><head><title>${esc(event.name)}</title><style>
      body{font-family:'Plus Jakarta Sans',system-ui,sans-serif;text-align:center;padding:48px;color:#0A0A0A}
      .rule{width:120px;height:2px;background:#C99A3B;margin:12px auto 20px}
      h1{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:64px;margin:0}
      p{font-size:24px;margin:8px 0}
      img{width:440px;height:440px;margin:24px auto;display:block}
      .price{font-size:40px;font-weight:700}
    </style></head><body>
      <h1>Medal engraving</h1><div class="rule"></div>
      <p class="price">${esc(formatCents(event.price_cents))} per medal</p>
      <p>Scan to order. We'll tell you when it's ready.</p>
      <img src="${qr}" alt="QR code to order engraving">
      <p>${esc(event.name)}</p>
    </body></html>`)
    w.document.close()
    w.focus()
    w.onload = () => w.print()
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(event.public_url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Modal title="Order QR code" onClose={onClose}>
      <div className="flex flex-col items-center gap-4">
        {qr ? <img src={qr} alt={`QR code linking to ${event.public_url}`} width={260} height={260} /> : <Spinner />}
        <p className="text-sm text-center" style={{ color: 'var(--ms-text-mid)' }}>
          Parents scan this to order. Print it as a sign for the stall.
        </p>
        <code className="text-xs break-all text-center" style={{ color: 'var(--ms-text-mid)' }}>{event.public_url}</code>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={copyLink}><Copy size={14} />{copied ? 'Copied' : 'Copy link'}</Button>
          <Button onClick={printSign} disabled={!qr}><Printer size={14} />Print sign</Button>
        </div>
      </div>
    </Modal>
  )
}

export default function EngravingEventsPage() {
  const [showNew, setShowNew] = useState(false)
  const [qrEvent, setQrEvent] = useState<EngravingEvent | null>(null)
  const { data: events, isLoading } = useQuery({
    queryKey: ['engraving-events'],
    queryFn: () => listEngravingEvents().then((r) => r.data),
  })

  return (
    <div>
      <PageHeader title="Engraving Events" action={<Button onClick={() => setShowNew(true)}><Plus size={14} />New event</Button>} />
      {isLoading ? (
        <Spinner />
      ) : !events?.length ? (
        <EmptyState message="No engraving events yet. Create one for your next meet and print the QR sign for the stall." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {events.map((ev) => (
            <Card key={ev.id} className="p-5 flex flex-col gap-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{ev.name}</h2>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>
                    {[formatEventDate(ev.event_date), ev.location].filter(Boolean).join(' · ') || 'No date set'}
                  </p>
                </div>
                <span
                  className="shrink-0 rounded-[var(--ms-radius)] px-2.5 py-1 text-[11px] font-bold"
                  style={{
                    background: ev.status === 'open' ? 'var(--ms-badge-green-bg, #DDF3E4)' : 'var(--ms-badge-neutral-bg, #E8E4DA)',
                    color: ev.status === 'open' ? 'var(--ms-badge-green-text, #1F5F3A)' : 'var(--ms-text-mid)',
                  }}
                >
                  {STATUS_LABEL[ev.status]}
                </span>
              </div>
              <dl className="grid grid-cols-3 gap-2 text-center">
                <div><dt className="text-[11px]" style={{ color: 'var(--ms-text-mid)' }}>Waiting</dt><dd className="text-lg font-bold">{ev.stats.waiting + ev.stats.engraving}</dd></div>
                <div><dt className="text-[11px]" style={{ color: 'var(--ms-text-mid)' }}>Medals</dt><dd className="text-lg font-bold">{ev.stats.medals_total}</dd></div>
                <div><dt className="text-[11px]" style={{ color: 'var(--ms-text-mid)' }}>Taken</dt><dd className="text-lg font-bold">{formatCents(ev.stats.paid_cents)}</dd></div>
              </dl>
              <div className="flex gap-2">
                <Link
                  to={`/engraving/${ev.id}`}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-[13px] font-semibold"
                  style={{ background: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }}
                >
                  <Award size={14} />Open queue
                </Link>
                <Button variant="secondary" onClick={() => setQrEvent(ev)}><QrCode size={14} />QR</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {showNew && <NewEventModal onClose={() => setShowNew(false)} />}
      {qrEvent && <EngravingQrModal event={qrEvent} onClose={() => setQrEvent(null)} />}
    </div>
  )
}
