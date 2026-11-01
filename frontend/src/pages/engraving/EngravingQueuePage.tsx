import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, Pause, Play, Plus, Printer, QrCode, RotateCcw, Search, SkipForward } from 'lucide-react'
import { Button, Card, Input, Modal, Select, Spinner } from '@/components/ui'
import MedalPreview from '@/components/engraving/MedalPreview'
import { EngravingQrModal } from './EngravingEventsPage'
import { ordersInBunch, printTicketSheet, printTubTicket } from './printTicket'
import {
  ENGRAVING_PLACES,
  createWalkUpEngravingOrder,
  engravingMedalDone,
  engravingPlaceText,
  exportEngravingFile,
  LASER_SOFTWARE,
  type LaserSoftware,
  getEngravingQueue,
  resendEngravingReady,
  startEngravingOrder,
  updateEngravingEvent,
  updateEngravingOrder,
  type EngravingOrder,
  type EngravingOrderStatus,
  type EngravingPlace,
} from '@/lib/api/engraving'
import { getApiErrorMessage } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const STATUS_PILL: Record<EngravingOrderStatus, { label: string; bg: string; fg: string }> = {
  engraving: { label: 'Engraving', bg: 'var(--ms-badge-orange-bg, #FCE7C2)', fg: 'var(--ms-badge-orange-text, #7A4B00)' },
  waiting: { label: 'Waiting', bg: 'var(--ms-badge-neutral-bg, #E8E4DA)', fg: 'var(--ms-text)' },
  ready: { label: 'Ready', bg: 'var(--ms-badge-blue-bg, #DCE8FB)', fg: 'var(--ms-badge-blue-text, #1E3A8A)' },
  collected: { label: 'Collected', bg: 'var(--ms-surface-alt, #EEF0F2)', fg: 'var(--ms-text-mid)' },
  cancelled: { label: 'Cancelled', bg: 'var(--ms-surface-alt, #EEF0F2)', fg: 'var(--ms-text-mid)' },
}

const SMS_NOTE: Record<string, string> = {
  sent: 'texted',
  dry_run: 'text logged (SMS not configured)',
  failed: 'text failed',
  skipped: 'no text',
}

type Filter = 'active' | 'ready' | 'all'

function StatusPill({ order }: { order: EngravingOrder }) {
  const s = STATUS_PILL[order.status]
  const note = order.status === 'ready' && order.ready_sms_status ? ` · ${SMS_NOTE[order.ready_sms_status] ?? order.ready_sms_status}` : ''
  return (
    <span className="inline-block whitespace-nowrap rounded-[var(--ms-radius)] px-2.5 py-1 text-[11px] font-bold" style={{ background: s.bg, color: s.fg }}>
      {s.label}{note}
    </span>
  )
}

function WalkUpModal({ eventId, onClose }: { eventId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [line2, setLine2] = useState('')
  const [place, setPlace] = useState<EngravingPlace>('1st')
  const [qty, setQty] = useState('1')
  const [phone, setPhone] = useState('')
  const [paid, setPaid] = useState(true)

  const create = useMutation({
    mutationFn: () =>
      createWalkUpEngravingOrder(eventId, {
        athlete_name: name.trim(),
        line2: line2.trim() || null,
        place,
        qty: Math.max(1, parseInt(qty || '1', 10)),
        phone: phone.trim() || null,
        paid,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engraving-queue', eventId] })
      onClose()
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (name.trim()) create.mutate()
  }

  return (
    <Modal title="Walk-up order" onClose={onClose} closeDisabled={create.isPending}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex justify-center"><MedalPreview name={name} line2={line2} place={place} size={160} /></div>
        <Input label="Athlete's name" value={name} onChange={(e) => setName(e.target.value)} maxLength={24} required autoFocus />
        <Input label="Second line" value={line2} onChange={(e) => setLine2(e.target.value)} maxLength={28} placeholder="Optional" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="Place" value={place} onChange={(e) => setPlace(e.target.value as EngravingPlace)}>
            {ENGRAVING_PLACES.map((p) => <option key={p} value={p}>{p === 'None' ? 'No place' : p}</option>)}
          </Select>
          <Input label="Medals" type="number" min="1" max="20" value={qty} onChange={(e) => setQty(e.target.value)} />
        </div>
        <Input label="Mobile (for the ready text)" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Optional" />
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
          <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} />
          Paid now
        </label>
        {create.isError && <p className="text-sm" role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(create.error, "Couldn't add the order.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={create.isPending}>Cancel</Button>
          <Button type="submit" disabled={!name.trim() || create.isPending}>{create.isPending ? 'Adding…' : 'Add to queue'}</Button>
        </div>
      </form>
    </Modal>
  )
}

export default function EngravingQueuePage() {
  const { eventId } = useParams<{ eventId: string }>()
  const qc = useQueryClient()
  const [filter, setFilter] = useState<Filter>('active')
  const [showWalkUp, setShowWalkUp] = useState(false)
  const [showQr, setShowQr] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [software, setSoftware] = useState<LaserSoftware>(() => {
    try {
      const saved = localStorage.getItem('engraving-laser-software')
      return LASER_SOFTWARE.some((x) => x.value === saved) ? (saved as LaserSoftware) : 'xtool'
    } catch {
      return 'xtool'
    }
  })
  const [exportLimit, setExportLimit] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['engraving-queue', eventId],
    queryFn: () => getEngravingQueue(eventId!).then((r) => r.data),
    enabled: !!eventId,
    refetchInterval: 8000,
  })

  const refresh = () => qc.invalidateQueries({ queryKey: ['engraving-queue', eventId] })
  const onError = (err: unknown) => setActionError(getApiErrorMessage(err, 'That didn’t work. Please try again.'))
  const onSuccess = () => {
    setActionError(null)
    refresh()
  }

  const start = useMutation({ mutationFn: (id: string) => startEngravingOrder(id), onSuccess, onError })
  const done = useMutation({ mutationFn: (id: string) => engravingMedalDone(id), onSuccess, onError })
  const patch = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateEngravingOrder>[1] }) => updateEngravingOrder(id, data),
    onSuccess,
    onError,
  })
  const resend = useMutation({ mutationFn: (id: string) => resendEngravingReady(id), onSuccess, onError })
  const setEventStatus = useMutation({
    mutationFn: (status: 'open' | 'paused' | 'closed') => updateEngravingEvent(eventId!, { status }),
    onSuccess: () => {
      onSuccess()
      qc.invalidateQueries({ queryKey: ['engraving-events'] })
    },
    onError,
  })

  const orders = useMemo(() => data?.orders ?? [], [data])
  const active = useMemo(() => orders.filter((o) => o.status === 'waiting' || o.status === 'engraving'), [orders])
  const current = active.find((o) => o.status === 'engraving') ?? null
  const upNext = active.filter((o) => o.id !== current?.id)
  const term = search.trim().toLowerCase()
  // Searching looks across every order, whatever the filter: order number, ticket, name or last digits of the mobile.
  const shown = orders.filter((o) =>
    term
      ? [o.order_number, o.ticket_number ?? '', o.athlete_name, o.line2 ?? ''].some((v) => v.toLowerCase().includes(term)) ||
        (/^\d{3,}$/.test(term) && (o.phone ?? '').replace(/\D/g, '').endsWith(term))
      : filter === 'all' ? true : filter === 'ready' ? o.status === 'ready' : o.status === 'waiting' || o.status === 'engraving',
  )
  const bunchOf = (o: EngravingOrder) => ordersInBunch(o, orders)
  const collectAll = (o: EngravingOrder) => {
    const mates = bunchOf(o).filter((m) => m.status === 'ready')
    mates.forEach((m) => patch.mutate({ id: m.id, data: { status: 'collected', paid: true } }))
  }
  const busy = start.isPending || done.isPending || patch.isPending || resend.isPending

  async function downloadCsv() {
    if (!data) return
    setExporting(true)
    try {
      const res = await exportEngravingFile(data.event.id, software, exportLimit ? Number(exportLimit) : undefined)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${data.event.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'engraving'}-${software}.${LASER_SOFTWARE.find((x) => x.value === software)?.ext ?? 'csv'}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      onError(err)
    } finally {
      setExporting(false)
    }
  }

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return <p style={{ color: 'var(--ms-text-mid)' }}>This event couldn't be loaded. <Link to="/engraving" className="underline">Back to events</Link></p>
  }

  const { event } = data
  const s = event.stats
  const lastMedal = current ? current.medals_done + 1 >= current.qty : false

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Link to="/engraving" className="inline-flex items-center gap-1 text-xs font-medium mb-2" style={{ color: 'var(--ms-text-mid)' }}>
            <ArrowLeft size={14} />All events
          </Link>
          <h1 className="ms-display text-[26px] leading-tight truncate" style={{ color: 'var(--ms-text)' }}>{event.name}</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-mid)' }}>
            {event.status === 'open' ? 'Taking orders' : event.status === 'paused' ? 'Orders paused' : 'Closed'} · {s.waiting + s.engraving} waiting · {s.ready} ready · {s.medals_remaining} medals to go · {formatCents(s.paid_cents)} taken
            {s.unpaid_cents > 0 && ` · ${formatCents(s.unpaid_cents)} unpaid`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setShowQr(true)}><QrCode size={14} />QR</Button>
          <label className="sr-only" htmlFor="engr-laser-software">Laser software</label>
          <select
            id="engr-laser-software"
            value={software}
            onChange={(e) => {
              const v = e.target.value as LaserSoftware
              setSoftware(v)
              try { localStorage.setItem('engraving-laser-software', v) } catch { /* ignore */ }
            }}
            className="h-11 px-2 text-sm"
            style={{ border: '1px solid var(--ms-border-strong, var(--ms-border))', background: 'var(--ms-surface)', color: 'var(--ms-text)', borderRadius: 'var(--ms-radius)' }}
          >
            {LASER_SOFTWARE.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
          </select>
          <label className="sr-only" htmlFor="engr-export-limit">How many medals</label>
          <select
            id="engr-export-limit"
            value={exportLimit}
            onChange={(e) => setExportLimit(e.target.value)}
            className="h-11 px-2 text-sm"
            style={{ border: '1px solid var(--ms-border-strong, var(--ms-border))', background: 'var(--ms-surface)', color: 'var(--ms-text)', borderRadius: 'var(--ms-radius)' }}
          >
            <option value="">All medals</option>
            <option value="10">Next 10</option>
            <option value="20">Next 20</option>
          </select>
          <Button variant="secondary" onClick={downloadCsv} disabled={exporting || s.medals_remaining === 0}><Download size={14} />{exporting ? 'Exporting…' : 'Export for laser'}</Button>
          {event.status === 'open' ? (
            <Button variant="secondary" onClick={() => setEventStatus.mutate('paused')} disabled={setEventStatus.isPending}><Pause size={14} />Pause orders</Button>
          ) : (
            <Button variant="secondary" onClick={() => setEventStatus.mutate('open')} disabled={setEventStatus.isPending}><Play size={14} />Resume orders</Button>
          )}
          <Button variant="secondary" onClick={() => {
            const from = Number(window.prompt('Print tear-off tickets starting from number…', '1'))
            const count = Number(window.prompt('How many tickets?', '50'))
            if (from > 0 && count > 0 && count <= 500 && !printTicketSheet(event.name, Math.floor(from), Math.floor(count))) setActionError('Allow pop-ups to print.')
          }}><Printer size={14} />Ticket sheet</Button>
          <Button onClick={() => setShowWalkUp(true)}><Plus size={14} />Walk-up order</Button>
        </div>
      </div>

      {actionError && (
        <p role="alert" className="text-sm rounded-md px-3 py-2" style={{ color: 'var(--ms-error)', background: 'var(--ms-badge-alert-bg)' }}>{actionError}</p>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card className="p-5 flex flex-col gap-4" style={current ? { borderColor: 'var(--ms-accent)', borderWidth: 2 } : undefined}>
            {current ? (
              <>
                <div className="flex items-center justify-between text-xs font-bold uppercase tracking-[0.12em]">
                  <span style={{ color: 'var(--ms-accent)' }}>Now engraving</span>
                  <span className="normal-case tracking-normal font-semibold" style={{ color: 'var(--ms-text-mid)' }}>
                    {current.order_number} · medal {Math.min(current.medals_done + 1, current.qty)} of {current.qty}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <MedalPreview name={current.athlete_name} line2={current.line2} place={current.place} size={112} />
                  <div className="min-w-0">
                    <p className="text-3xl font-bold leading-none break-words" style={{ color: 'var(--ms-text)' }}>{current.athlete_name}</p>
                    {current.line2 && <p className="mt-1 text-base">{current.line2}</p>}
                    {engravingPlaceText(current.place) && <p className="text-sm font-semibold" style={{ color: 'var(--ms-text-mid)' }}>{engravingPlaceText(current.place)}</p>}
                  </div>
                </div>
                <div className="flex items-center justify-between rounded-md px-3 py-2 text-xs" style={{ background: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>
                  <span>{current.paid ? `Paid ${formatCents(current.amount_cents)}` : `Unpaid · ${formatCents(current.amount_cents)}`}</span>
                  <span>{current.phone ? `Text to ${current.phone.slice(0, 4)} ••• ${current.phone.slice(-3)}` : 'No mobile'}</span>
                </div>
                <button
                  type="button"
                  onClick={() => done.mutate(current.id)}
                  disabled={busy}
                  className="h-14 rounded-[var(--ms-radius)] text-base font-bold disabled:opacity-60"
                  style={{ background: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }}
                >
                  {lastMedal ? 'Done — order ready' : 'Done — next medal'}
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => patch.mutate({ id: current.id, data: { paid: !current.paid } })} disabled={busy}>
                    {current.paid ? 'Mark unpaid' : 'Mark paid'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => (upNext[0] ? start.mutate(upNext[0].id) : patch.mutate({ id: current.id, data: { status: 'waiting' } }))}
                    disabled={busy}
                  >
                    <SkipForward size={14} />Skip for now
                  </Button>
                </div>
              </>
            ) : upNext[0] ? (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>Nothing on the laser. Next up is {upNext[0].order_number}, {upNext[0].athlete_name}.</p>
                <Button onClick={() => start.mutate(upNext[0].id)} disabled={busy}><Play size={14} />Start {upNext[0].order_number}</Button>
              </div>
            ) : (
              <p className="py-6 text-center text-sm" style={{ color: 'var(--ms-text-mid)' }}>Queue's clear. New orders show up here by themselves.</p>
            )}
          </Card>

          {upNext.length > 0 && (
            <Card className="p-4 flex flex-col gap-2">
              <p className="text-xs font-bold uppercase tracking-[0.12em]" style={{ color: 'var(--ms-text-mid)' }}>Up next</p>
              {upNext.slice(0, 4).map((o) => (
                <div key={o.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-semibold truncate">{o.order_number} · {o.athlete_name}{o.qty > 1 ? ` ×${o.qty}` : ''}</span>
                  <span className="truncate" style={{ color: 'var(--ms-text-mid)' }}>{[o.line2, o.place !== 'None' ? o.place : null].filter(Boolean).join(' · ')}</span>
                </div>
              ))}
              {upNext.length > 4 && <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>+{upNext.length - 4} more</p>}
            </Card>
          )}
        </div>

        <Card className="flex flex-col min-w-0 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
            <h2 className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>Orders</h2>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-mid)' }} aria-hidden />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search orders"
                placeholder="Order, ticket, name or last 4 of mobile"
                className="h-9 w-64 pl-8 pr-3 text-sm"
                style={{ border: '1px solid var(--ms-border-strong, var(--ms-border))', background: 'var(--ms-surface)', color: 'var(--ms-text)', borderRadius: 'var(--ms-radius)' }}
              />
            </div>
            <div className="flex gap-1.5" role="group" aria-label="Filter orders">
              {(['active', 'ready', 'all'] as Filter[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={filter === f}
                  onClick={() => setFilter(f)}
                  className="h-9 rounded-[var(--ms-radius)] px-3.5 text-xs font-semibold"
                  style={{
                    background: filter === f ? 'var(--ms-text)' : 'var(--ms-surface)',
                    color: filter === f ? 'var(--ms-bg)' : 'var(--ms-text)',
                    border: `1px solid ${filter === f ? 'var(--ms-text)' : 'var(--ms-border)'}`,
                  }}
                >
                  {f === 'active' ? `In queue (${active.length})` : f === 'ready' ? `Ready (${s.ready})` : 'All'}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider" style={{ color: 'var(--ms-text-mid)' }}>
                  <th className="px-4 py-2 font-semibold">Order</th>
                  <th className="px-3 py-2 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Place</th>
                  <th className="px-3 py-2 font-semibold">Qty</th>
                  <th className="px-3 py-2 font-semibold">Paid</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-4 py-2 font-semibold sticky right-0" style={{ background: 'var(--ms-surface)' }}><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: 'var(--ms-text-mid)' }}>Nothing here yet.</td></tr>
                )}
                {shown.map((o) => (
                  <tr key={o.id} style={{ borderTop: '1px solid var(--ms-border)' }}>
                    <td className="px-4 py-2.5 font-semibold whitespace-nowrap">
                      {o.order_number}
                      {o.ticket_number && <span className="block text-xs font-normal" style={{ color: 'var(--ms-text-mid)' }}>Ticket {o.ticket_number}</span>}
                      {o.group_id && <span className="block text-xs font-normal" style={{ color: 'var(--ms-text-mid)' }}>with {bunchOf(o).filter((m) => m.id !== o.id).map((m) => m.order_number).join(', ')}</span>}
                    </td>
                    <td className="px-3 py-2.5"><span className="font-semibold">{o.athlete_name}</span>{o.line2 && <span className="block text-xs" style={{ color: 'var(--ms-text-mid)' }}>{o.line2}</span>}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap">{o.place === 'None' ? '' : o.place}</td>
                    <td className="px-3 py-2.5">{o.medals_done > 0 && o.medals_done < o.qty ? `${o.medals_done}/${o.qty}` : o.qty}</td>
                    <td className="px-3 py-2.5">
                      <label className="inline-flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={o.paid}
                          disabled={busy || o.status === 'cancelled'}
                          onChange={() => patch.mutate({ id: o.id, data: { paid: !o.paid } })}
                          aria-label={`${o.order_number} paid`}
                        />
                        <span className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>{formatCents(o.amount_cents)}</span>
                      </label>
                    </td>
                    <td className="px-3 py-2.5"><StatusPill order={o} /></td>
                    <td className="px-4 py-2.5 sticky right-0" style={{ background: 'var(--ms-surface)', boxShadow: '-8px 0 8px -8px rgba(10,10,10,0.18)' }}>
                      <div className="flex justify-end gap-1.5 whitespace-nowrap">
                        {o.status === 'waiting' && <Button size="sm" variant="secondary" onClick={() => start.mutate(o.id)} disabled={busy}>Start</Button>}
                        {(o.status === 'waiting' || o.status === 'engraving') && (
                          <Button size="sm" variant="ghost" onClick={() => { if (window.confirm(`Cancel ${o.order_number} for ${o.athlete_name}?`)) patch.mutate({ id: o.id, data: { status: 'cancelled' } }) }} disabled={busy}>Cancel</Button>
                        )}
                        <Button size="sm" variant="ghost" aria-label={`Print ticket for ${o.order_number}`} title="Print tub ticket" onClick={() => { if (!printTubTicket(event, bunchOf(o))) setActionError('Allow pop-ups to print.') }}>
                          <Printer size={13} />
                        </Button>
                        {o.status === 'ready' && (
                          <>
                            {bunchOf(o).filter((m) => m.status === 'ready').length > 1 && (
                              <Button size="sm" onClick={() => collectAll(o)} disabled={busy}>Collect all</Button>
                            )}
                            <Button size="sm" onClick={() => patch.mutate({ id: o.id, data: { status: 'collected', paid: true } })} disabled={busy}>Collected</Button>
                            {o.phone && <Button size="sm" variant="ghost" onClick={() => resend.mutate(o.id)} disabled={busy}>Resend text</Button>}
                          </>
                        )}
                        {(o.status === 'collected' || o.status === 'cancelled' || o.status === 'ready') && (
                          <Button size="sm" variant="ghost" aria-label={`Re-engrave ${o.order_number}`} title="Put back in the queue" onClick={() => patch.mutate({ id: o.id, data: { status: 'waiting' } })} disabled={busy}>
                            <RotateCcw size={13} />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {showWalkUp && <WalkUpModal eventId={event.id} onClose={() => setShowWalkUp(false)} />}
      {showQr && <EngravingQrModal event={event} onClose={() => setShowQr(false)} />}
    </div>
  )
}
